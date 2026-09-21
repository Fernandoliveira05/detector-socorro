"""Parâmetros e utilidades compartilhadas (features MFCC compatíveis com ESP32)."""
import numpy as np, librosa
from pathlib import Path

SR        = 16000
CLIP_S    = 1.0
CLIP_LEN  = int(SR * CLIP_S)        # 16000 amostras
N_MFCC    = 16
N_MELS     = 40
WIN_LEN   = 480                     # 30 ms
HOP_LEN   = 320                     # 20 ms  -> ~49 frames
N_FFT     = 512
N_FRAMES  = 1 + (CLIP_LEN - WIN_LEN) // HOP_LEN   # 49

def fix_length(y):
    """Padroniza para CLIP_LEN amostras, centralizando pela energia."""
    if len(y) > CLIP_LEN:
        # janela de CLIP_LEN com maior energia
        e = y ** 2
        k = np.ones(CLIP_LEN)
        s = np.convolve(e, k, "valid")
        i = int(np.argmax(s))
        y = y[i:i + CLIP_LEN]
    elif len(y) < CLIP_LEN:
        pad = CLIP_LEN - len(y)
        y = np.pad(y, (pad // 2, pad - pad // 2))
    return y.astype(np.float32)

_NORM_PATH = Path(__file__).resolve().parents[1] / "models" / "feat_norm.npz"
_norm = None   # cache: (mean[16], std[16]) ou False se não existir

def _load_norm():
    global _norm
    if _norm is None:
        if _NORM_PATH.exists():
            d = np.load(_NORM_PATH); _norm = (d["mean"], d["std"])
        else:
            _norm = False
    return _norm

def reset_norm_cache():
    global _norm
    _norm = None

# ---- tabelas do MFCC no MESMO padrão do firmware (features.cpp) ----
_hann = (0.5 * (1 - np.cos(2*np.pi*np.arange(WIN_LEN)/WIN_LEN))).astype(np.float32)  # Hann periódica
def _hz2mel(f): return 2595.0*np.log10(1.0 + f/700.0)
def _mel2hz(m): return 700.0*(10.0**(m/2595.0) - 1.0)
_melpts = _mel2hz(_hz2mel(20.0) + (_hz2mel(SR/2)-_hz2mel(20.0))*np.arange(N_MELS+2)/(N_MELS+1))
_melbin = np.clip(np.floor((N_FFT+1)*_melpts/SR).astype(int), 0, N_FFT//2)
_MELFB = np.zeros((N_MELS, N_FFT//2 + 1), np.float32)     # triângulos crus (sem norm. Slaney)
for _m in range(N_MELS):
    _lo, _mid, _hi = _melbin[_m], _melbin[_m+1], _melbin[_m+2]
    for _k in range(_lo, _mid):
        if _mid > _lo: _MELFB[_m, _k] = (_k-_lo)/(_mid-_lo)
    for _k in range(_mid, _hi):
        if _hi > _mid: _MELFB[_m, _k] = (_hi-_k)/(_hi-_mid)
_DCT = np.zeros((N_MFCC, N_MELS), np.float32)             # DCT-II ortonormal
for _c in range(N_MFCC):
    _s = np.sqrt(1.0/N_MELS) if _c == 0 else np.sqrt(2.0/N_MELS)
    _DCT[_c] = _s*np.cos(np.pi*_c*(2*np.arange(N_MELS)+1)/(2*N_MELS))

def _mfcc_raw(y):
    """MFCC (N_FRAMES x N_MFCC) IGUAL ao firmware: pico->0.95, Hann, FFT 512,
    mel triangular cru, log natural, DCT-II. Sem normalização de estatística."""
    peak = np.max(np.abs(y))
    if peak > 1e-6:
        y = y / peak * 0.95
    frames = np.zeros((N_FRAMES, N_FFT), np.float32)
    for f in range(N_FRAMES):
        s = f*HOP_LEN; seg = y[s:s+WIN_LEN]
        frames[f, :len(seg)] = seg * _hann[:len(seg)]
    pw = np.abs(np.fft.rfft(frames, axis=1))**2           # (N_FRAMES, 257) potência
    mel = np.log(pw @ _MELFB.T + 1e-10)                   # (N_FRAMES, 40) log-mel
    return (mel @ _DCT.T).astype(np.float32)              # (N_FRAMES, 16) MFCC

def mfcc(y, normalize=True):
    """MFCC 1s@16k. Normalização GLOBAL FIXA (média/desvio por-canal do treino):
    determinística e estável (silêncio continua silêncio). Se o arquivo de
    estatísticas não existir, cai no modo por-utterance (compatibilidade)."""
    m = _mfcc_raw(y)
    if not normalize:
        return m
    n = _load_norm()
    if n:                                      # normalização global fixa
        mean, std = n
        m = (m - mean) / std
    else:                                      # fallback: por-utterance
        m = (m - m.mean()) / (m.std() + 1e-6)
    return m.astype(np.float32)

def compute_and_save_norm(files, load_fn):
    """Calcula média/desvio por-canal do MFCC sobre os arquivos (SÓ TREINO) e salva."""
    ms = np.concatenate([_mfcc_raw(load_fn(f)) for f in files], axis=0)  # (N*49,16)
    mean = ms.mean(axis=0); std = ms.std(axis=0) + 1e-6
    _NORM_PATH.parent.mkdir(parents=True, exist_ok=True)
    np.savez(_NORM_PATH, mean=mean.astype(np.float32), std=std.astype(np.float32))
    reset_norm_cache()
    return mean, std
