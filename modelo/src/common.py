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

def _mfcc_raw(y):
    """MFCC (N_FRAMES x N_MFCC) SEM normalização de estatística. Pico->0.95."""
    peak = np.max(np.abs(y))
    if peak > 1e-6:
        y = y / peak * 0.95
    m = librosa.feature.mfcc(
        y=y, sr=SR, n_mfcc=N_MFCC, n_fft=N_FFT,
        win_length=WIN_LEN, hop_length=HOP_LEN, n_mels=N_MELS,
        fmin=20, fmax=SR // 2)
    m = m[:, :N_FRAMES].T                      # (frames, coef)
    if m.shape[0] < N_FRAMES:
        m = np.pad(m, ((0, N_FRAMES - m.shape[0]), (0, 0)))
    return m.astype(np.float32)

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
