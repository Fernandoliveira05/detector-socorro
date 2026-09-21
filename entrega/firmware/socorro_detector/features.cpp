// ============================================================================
// features.cpp — RMS + MFCC no ESP32 (versão enxuta de RAM).
// Entrada int16; sem matriz mel guardada (calculada na hora); sem cópia extra.
// Espelha projeto/src/common.py (com normalização global de feat_norm.h).
// ============================================================================
#include "features.h"
#include "feat_norm.h"      // MFCC_MEAN[16], MFCC_STD[16]
#include <math.h>
#include <string.h>

static float hann_[WIN_LEN];
static int   melbin_[N_MELS + 2];        // bordas dos filtros mel (em bins de FFT)
static float dct_[N_MFCC][N_MELS];

// ---------- FFT radix-2 iterativa (512 pontos, in-place) ----------
static void fft512(float* re, float* im) {
  const int n = N_FFT;
  for (int i = 1, j = 0; i < n; i++) {
    int bit = n >> 1;
    for (; j & bit; bit >>= 1) j ^= bit;
    j ^= bit;
    if (i < j) { float t=re[i];re[i]=re[j];re[j]=t; t=im[i];im[i]=im[j];im[j]=t; }
  }
  for (int len = 2; len <= n; len <<= 1) {
    float ang = -2.0f * (float)M_PI / len, wr = cosf(ang), wi = sinf(ang);
    for (int i = 0; i < n; i += len) {
      float cr = 1.0f, ci = 0.0f;
      for (int k = 0; k < len/2; k++) {
        int a = i+k, b = i+k+len/2;
        float xr = re[b]*cr - im[b]*ci, xi = re[b]*ci + im[b]*cr;
        re[b] = re[a]-xr; im[b] = im[a]-xi; re[a] += xr; im[a] += xi;
        float ncr = cr*wr - ci*wi; ci = cr*wi + ci*wr; cr = ncr;
      }
    }
  }
}

static float hz_to_mel(float f){ return 2595.0f*log10f(1.0f+f/700.0f); }
static float mel_to_hz(float m){ return 700.0f*(powf(10.0f,m/2595.0f)-1.0f); }

void features_init() {
  for (int i=0;i<WIN_LEN;i++)
    hann_[i] = 0.5f*(1.0f - cosf(2.0f*(float)M_PI*i/WIN_LEN));
  float m0 = hz_to_mel(FMIN), m1 = hz_to_mel(FMAX);
  for (int i=0;i<N_MELS+2;i++){
    float hz = mel_to_hz(m0 + (m1-m0)*i/(N_MELS+1));
    melbin_[i] = (int)floorf((N_FFT+1)*hz/SR);
    if (melbin_[i] > N_FFT/2) melbin_[i] = N_FFT/2;
  }
  for (int c=0;c<N_MFCC;c++)
    for (int m=0;m<N_MELS;m++){
      float s = (c==0)? sqrtf(1.0f/N_MELS) : sqrtf(2.0f/N_MELS);
      dct_[c][m] = s*cosf((float)M_PI*c*(2*m+1)/(2*N_MELS));
    }
}

// amostra p (0..CLIP_LEN-1) da janela que termina em end_idx, lida do ring circular
static inline float sample(const int16_t* ring, int end_idx, int p){
  int idx = (end_idx - CLIP_LEN + p) % RING_LEN;
  if (idx < 0) idx += RING_LEN;
  return ring[idx] / 32768.0f;
}

float compute_rms(const int16_t* ring, int end_idx){
  double s=0; for(int p=0;p<CLIP_LEN;p++){ float v=sample(ring,end_idx,p); s+=v*v; }
  return sqrtf((float)(s/CLIP_LEN));
}

void compute_mfcc(const int16_t* ring, int end_idx, float* out){
  // pico -> escala p/ 0.95 (invariância a volume, igual ao treino)
  float peak = 1e-6f;
  for (int p=0;p<CLIP_LEN;p++){ float a=sample(ring,end_idx,p); if(a<0)a=-a; if(a>peak)peak=a; }
  float scale = 0.95f / peak;
  memset(out, 0, sizeof(float)*N_FRAMES*N_MFCC);   // zera antes de acumular o DCT

  static float re[N_FFT], im[N_FFT], pw[N_FFT/2+1];
  for (int f=0; f<N_FRAMES; f++){
    int start = f*HOP_LEN;
    for (int i=0;i<N_FFT;i++){
      float v = 0.0f;
      if (i<WIN_LEN){ int p=start+i; if(p<CLIP_LEN) v = sample(ring,end_idx,p)*scale*hann_[i]; }
      re[i]=v; im[i]=0.0f;
    }
    fft512(re,im);
    for (int k=0;k<=N_FFT/2;k++) pw[k] = re[k]*re[k]+im[k]*im[k];
    // mel calculado na hora (triângulos), sem guardar matriz
    for (int m=0;m<N_MELS;m++){
      int lo=melbin_[m], mid=melbin_[m+1], hi=melbin_[m+2];
      float acc=0;
      for (int k=lo;  k<mid; k++) if(k>=0&&k<=N_FFT/2) acc += (float)(k-lo)/(mid-lo+1e-9f)*pw[k];
      for (int k=mid; k<hi;  k++) if(k>=0&&k<=N_FFT/2) acc += (float)(hi-k)/(hi-mid+1e-9f)*pw[k];
      float logmel = logf(acc+1e-10f);
      // acumula direto no DCT p/ não guardar vetor mel inteiro
      for (int c=0;c<N_MFCC;c++) out[f*N_MFCC+c] += dct_[c][m]*logmel;
    }
  }
  // normalização GLOBAL fixa por canal (feat_norm.h) — probabilidades estáveis
  for (int f=0; f<N_FRAMES; f++)
    for (int c=0;c<N_MFCC;c++)
      out[f*N_MFCC+c] = (out[f*N_MFCC+c] - MFCC_MEAN[c]) / MFCC_STD[c];
}
