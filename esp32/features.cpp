// ============================================================================
// features.cpp — RMS + MFCC no ESP32, espelhando projeto/src/common.py.
//
// Pipeline (por janela de 1s):
//   1) normaliza pico -> 0.95            (igual mfcc() do treino)
//   2) para cada frame (Hann, 480, hop 320): FFT 512 -> |.|^2
//   3) mel filterbank (40 bandas, 20..8000 Hz) -> log
//   4) DCT-II ortonormal -> 16 coeficientes (MFCC)
//   5) normalização média/desvio por-utterance
//
// OBS de paridade: librosa usa center=True (frames centrados com padding).
// Aqui usamos framing simples (center=False). É a principal fonte de diferença
// numérica vs. treino — ver "Discussão" no relatório. Calibrar antes de produção.
// ============================================================================
#include "features.h"
#include "feat_norm.h"      // MFCC_MEAN[16], MFCC_STD[16] (estatísticas globais do treino)
#include <math.h>
#include <string.h>

static float hann_[WIN_LEN];
static float melfb_[N_MELS][N_FFT/2 + 1];
static float dct_[N_MFCC][N_MELS];

// ---------- FFT radix-2 iterativa (512 pontos, in-place) ----------
static void fft512(float* re, float* im) {
  const int n = N_FFT;
  for (int i = 1, j = 0; i < n; i++) {           // bit-reversal
    int bit = n >> 1;
    for (; j & bit; bit >>= 1) j ^= bit;
    j ^= bit;
    if (i < j) { float t=re[i];re[i]=re[j];re[j]=t; t=im[i];im[i]=im[j];im[j]=t; }
  }
  for (int len = 2; len <= n; len <<= 1) {
    float ang = -2.0f * (float)M_PI / len;
    float wr = cosf(ang), wi = sinf(ang);
    for (int i = 0; i < n; i += len) {
      float cr = 1.0f, ci = 0.0f;
      for (int k = 0; k < len/2; k++) {
        int a = i+k, b = i+k+len/2;
        float xr = re[b]*cr - im[b]*ci;
        float xi = re[b]*ci + im[b]*cr;
        re[b] = re[a]-xr; im[b] = im[a]-xi;
        re[a] += xr;      im[a] += xi;
        float ncr = cr*wr - ci*wi; ci = cr*wi + ci*wr; cr = ncr;
      }
    }
  }
}

static float hz_to_mel(float f){ return 2595.0f*log10f(1.0f+f/700.0f); }
static float mel_to_hz(float m){ return 700.0f*(powf(10.0f,m/2595.0f)-1.0f); }

void features_init() {
  for (int i=0;i<WIN_LEN;i++)                     // Hann periódica (fftbins=True)
    hann_[i] = 0.5f*(1.0f - cosf(2.0f*(float)M_PI*i/WIN_LEN));

  // mel filterbank triangular (aprox. Slaney/HTK)
  float m0 = hz_to_mel(FMIN), m1 = hz_to_mel(FMAX);
  float mpts[N_MELS+2];
  for (int i=0;i<N_MELS+2;i++) mpts[i] = mel_to_hz(m0 + (m1-m0)*i/(N_MELS+1));
  int   bins[N_MELS+2];
  for (int i=0;i<N_MELS+2;i++) bins[i] = (int)floorf((N_FFT+1)*mpts[i]/SR);
  memset(melfb_,0,sizeof(melfb_));
  for (int m=1;m<=N_MELS;m++){
    for (int k=bins[m-1]; k<bins[m]; k++)
      if(k>=0&&k<=N_FFT/2) melfb_[m-1][k] = (float)(k-bins[m-1])/(bins[m]-bins[m-1]+1e-9f);
    for (int k=bins[m]; k<bins[m+1]; k++)
      if(k>=0&&k<=N_FFT/2) melfb_[m-1][k] = (float)(bins[m+1]-k)/(bins[m+1]-bins[m]+1e-9f);
  }
  // matriz DCT-II ortonormal
  for (int c=0;c<N_MFCC;c++)
    for (int m=0;m<N_MELS;m++){
      float s = (c==0)? sqrtf(1.0f/N_MELS) : sqrtf(2.0f/N_MELS);
      dct_[c][m] = s*cosf((float)M_PI*c*(2*m+1)/(2*N_MELS));
    }
}

float compute_rms(const float* x, int n){
  float s=0; for(int i=0;i<n;i++) s+=x[i]*x[i];
  return sqrtf(s/n);
}

void compute_mfcc(const float* clip_in, float* out){
  static float clip[CLIP_LEN];
  // 1) normaliza pico -> 0.95
  float peak=1e-6f; for(int i=0;i<CLIP_LEN;i++){ float a=fabsf(clip_in[i]); if(a>peak)peak=a; }
  float g = 0.95f/peak;
  for(int i=0;i<CLIP_LEN;i++) clip[i]=clip_in[i]*g;

  static float re[N_FFT], im[N_FFT];
  for (int f=0; f<N_FRAMES; f++){
    int start = f*HOP_LEN;
    // janela + zero-pad até N_FFT
    for (int i=0;i<N_FFT;i++){
      float v = 0.0f;
      if (i<WIN_LEN){ int idx=start+i; if(idx<CLIP_LEN) v=clip[idx]*hann_[i]; }
      re[i]=v; im[i]=0.0f;
    }
    fft512(re,im);
    // power spectrum -> mel -> log
    float mel[N_MELS];
    for (int m=0;m<N_MELS;m++){
      float acc=0;
      for (int k=0;k<=N_FFT/2;k++){
        float p = re[k]*re[k]+im[k]*im[k];
        acc += melfb_[m][k]*p;
      }
      mel[m]=logf(acc+1e-10f);      // log-mel (aprox. power_to_db)
    }
    // DCT -> MFCC, já normalizado por canal com estatísticas GLOBAIS do treino
    // (determinístico e estável; bate com common.py). NÃO usa média por-utterance.
    for (int c=0;c<N_MFCC;c++){
      float acc=0; for(int m=0;m<N_MELS;m++) acc+=dct_[c][m]*mel[m];
      out[f*N_MFCC+c] = (acc - MFCC_MEAN[c]) / MFCC_STD[c];
    }
  }
}
