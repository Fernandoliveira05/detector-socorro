"""Parâmetros e extração de features (MFCC) — IGUAIS no treino e no ESP32.
O MFCC aqui replica exatamente o features.cpp do firmware (Hann, FFT 512,
mel triangular, log natural, DCT-II) para garantir paridade treino↔dispositivo."""
import numpy as np, librosa
from pathlib import Path

SR = 16000
CLIP_LEN = 16000          # 1 s
N_MFCC, N_MELS = 16, 40
WIN_LEN, HOP_LEN, N_FFT = 480, 320, 512
N_FRAMES = 1 + (CLIP_LEN - WIN_LEN) // HOP_LEN   # 49

def fix_length(y):
    if len(y) > CLIP_LEN:
        e = np.convolve(y**2, np.ones(CLIP_LEN), "valid"); i = int(np.argmax(e)); y = y[i:i+CLIP_LEN]
    elif len(y) < CLIP_LEN:
        pad = CLIP_LEN - len(y); y = np.pad(y, (pad//2, pad-pad//2))
    return y.astype(np.float32)

# tabelas (idênticas a features.cpp)
_hann = (0.5*(1 - np.cos(2*np.pi*np.arange(WIN_LEN)/WIN_LEN))).astype(np.float32)
def _hz2mel(f): return 2595.0*np.log10(1.0 + f/700.0)
def _mel2hz(m): return 700.0*(10.0**(m/2595.0) - 1.0)
_melpts = _mel2hz(_hz2mel(20.0) + (_hz2mel(SR/2)-_hz2mel(20.0))*np.arange(N_MELS+2)/(N_MELS+1))
_melbin = np.clip(np.floor((N_FFT+1)*_melpts/SR).astype(int), 0, N_FFT//2)
_MELFB = np.zeros((N_MELS, N_FFT//2+1), np.float32)
for _m in range(N_MELS):
    _lo,_mid,_hi = _melbin[_m],_melbin[_m+1],_melbin[_m+2]
    for _k in range(_lo,_mid):
        if _mid>_lo: _MELFB[_m,_k]=(_k-_lo)/(_mid-_lo)
    for _k in range(_mid,_hi):
        if _hi>_mid: _MELFB[_m,_k]=(_hi-_k)/(_hi-_mid)
_DCT = np.zeros((N_MFCC, N_MELS), np.float32)
for _c in range(N_MFCC):
    _s = np.sqrt(1.0/N_MELS) if _c==0 else np.sqrt(2.0/N_MELS)
    _DCT[_c] = _s*np.cos(np.pi*_c*(2*np.arange(N_MELS)+1)/(2*N_MELS))

_NORM = Path(__file__).resolve().parent / "modelos" / "feat_norm.npz"
_norm = None
def _stats():
    global _norm
    if _norm is None: _norm = np.load(_NORM) if _NORM.exists() else False
    return _norm

def _mfcc_raw(y):
    peak = np.max(np.abs(y))
    if peak > 1e-6: y = y/peak*0.95
    frames = np.zeros((N_FRAMES, N_FFT), np.float32)
    for f in range(N_FRAMES):
        s = f*HOP_LEN; seg = y[s:s+WIN_LEN]; frames[f, :len(seg)] = seg*_hann[:len(seg)]
    pw = np.abs(np.fft.rfft(frames, axis=1))**2
    mel = np.log(pw @ _MELFB.T + 1e-10)
    return (mel @ _DCT.T).astype(np.float32)

def mfcc(y):
    m = _mfcc_raw(y); n = _stats()
    return ((m - n["mean"]) / n["std"] if n is not False else (m - m.mean())/(m.std()+1e-6)).astype(np.float32)
