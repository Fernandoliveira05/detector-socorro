#!/usr/bin/env python3
"""
Etapa 4: monta X/y de treino/val/teste.
- Split POR ARQUIVO (evita vazamento).
- Augmentation SÓ no treino (shift, ganho, ruído, pitch, stretch).
- Val/Teste = clipes REAIS originais (acurácia honesta).
Salva projeto/metadata/dataset.npz
"""
import sys, random
from pathlib import Path
import numpy as np, librosa
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (SR, CLIP_LEN, N_FRAMES, N_MFCC, fix_length, mfcc,
                    compute_and_save_norm)

PROJ = Path(__file__).resolve().parents[1]
DS   = PROJ / "dataset"
rng  = random.Random(1234)
np_rng = np.random.default_rng(1234)

N_TRAIN_PER_CLASS = 2500     # amostras (aug) por classe no treino

def list_files():
    pos = sorted((DS / "positives").glob("*.wav"))
    neg = []
    for sub in ["from_recordings", "pt_speech", "noise", "other_words",
                "loud_speech", "mic_user", "pc_neg", "mic_noise", "conversation",
                "inmp_speech"]:
        neg += sorted((DS / "negatives" / sub).glob("*.wav"))
    return pos, neg

def split(files, seed=7):
    r = random.Random(seed); f = files[:]; r.shuffle(f)
    n = len(f); a = int(0.70*n); b = int(0.85*n)
    return f[:a], f[a:b], f[b:]          # train, val, test

def load(path):
    y, _ = librosa.load(path, sr=SR, mono=True)
    return fix_length(y)

# ---- augmentation ----
NOISE_POOL = None
def noise_pool():
    global NOISE_POOL
    if NOISE_POOL is None:
        files = sorted((DS / "negatives" / "noise").glob("*.wav"))
        NOISE_POOL = [load(f) for f in rng.sample(files, min(60, len(files)))]
    return NOISE_POOL

def reverb(y):
    """Convolução com IR sintética (decaimento exponencial) = eco de sala."""
    L = int(SR * np_rng.uniform(0.05, 0.25))
    ir = np_rng.standard_normal(L) * np.exp(-np.arange(L)/(SR*0.05))
    ir[0] = 1.0
    out = np.convolve(y, ir)[:CLIP_LEN]
    return out

def augment(y, is_neg=False):
    # Augmentation CONSERVADORA (prioriza ESTABILIDADE da fronteira):
    # deslocamento pequeno + ruído leve. Sem reverb/time-stretch/pitch pesados,
    # que deixavam as probabilidades erráticas (saltos 0->0.9).
    y = y.copy()
    # time shift pequeno (±150 ms)
    s = np_rng.integers(-SR//7, SR//7)
    y = np.roll(y, s)
    # pitch shift SIMÉTRICO (±3 semitons) em positivos E negativos: dá robustez a
    # entonações diferentes SEM ensinar "agudo=socorro" (negativos também variam).
    if rng.random() < 0.6:
        y = librosa.effects.pitch_shift(y=y, sr=SR, n_steps=np_rng.uniform(-3, 3))
    # ruído leve só às vezes (SNR alto = pouco ruído)
    if rng.random() < 0.4:
        n = rng.choice(noise_pool())
        snr = np_rng.uniform(12, 28)
        ps = np.mean(y**2)+1e-9; pn = np.mean(n**2)+1e-9
        k = np.sqrt(ps/(pn*10**(snr/10)))
        y = y + k*n
    # ganho suave
    y = y * np_rng.uniform(0.7, 1.2)
    m = np.max(np.abs(y)) or 1.0
    if m > 1: y = y/m
    return fix_length(y)

def feats_real(files):
    return np.stack([mfcc(load(f)) for f in files]) if files else np.empty((0,N_FRAMES,N_MFCC))

PC_BOOST = 2.0     # peso in-domain moderado (6 enviesava demais p/ a voz do dono)

def is_pc(path):
    n = Path(path).name
    return (n.startswith("pc_") or n.startswith("pcneg_") or n.startswith("micnoise_")
            or n.startswith("mic_socorro_") or n.startswith("mic_neg_")
            or n.startswith("conv_"))

def feats_train(files, n_target, base_w=1.0, is_neg=False):
    out = []
    base = [load(f) for f in files]
    weights = [PC_BOOST if is_pc(f) else base_w for f in files]
    for i in range(n_target):
        if i < len(base):
            y = base[i]                                   # 1 passada determinística
        else:
            y = augment(rng.choices(base, weights=weights, k=1)[0], is_neg=is_neg)
        out.append(mfcc(y))
    return np.stack(out)

# pastas de variações de voz (etapa 13) — usadas SÓ no treino, ligadas ao pai
POS_VAR = PROJ / "dataset" / "positives_variants"
NEG_VAR = PROJ / "dataset" / "negatives_variants"

def with_variants(files, vardir):
    """Acrescenta as variações de voz de cada arquivo (mesmo stem). Só treino."""
    out = list(files)
    if vardir.exists():
        for f in files:
            out += sorted(vardir.glob(f"{f.stem}__v*.wav"))
    return out

def main():
    pos, neg = list_files()
    ptr, pva, pte = split(pos, 7)
    ntr, nva, nte = split(neg, 11)
    print(f"positivos  train/val/test = {len(ptr)}/{len(pva)}/{len(pte)}")
    print(f"negativos  train/val/test = {len(ntr)}/{len(nva)}/{len(nte)}")

    # normalização GLOBAL fixa: estatísticas SÓ do treino (sem vazamento)
    compute_and_save_norm(ptr + ntr, load)
    print("normalização global salva (models/feat_norm.npz)")

    # variações de voz DESLIGADAS (baseline estável) — reduzem estabilidade.
    # Para religar: USE_VARIANTS = True
    USE_VARIANTS = False
    ptr_v = with_variants(ptr, POS_VAR) if USE_VARIANTS else ptr
    ntr_v = with_variants(ntr, NEG_VAR) if USE_VARIANTS else ntr
    print(f"treino: pos {len(ptr_v)}  neg {len(ntr_v)}  (variações={'ON' if USE_VARIANTS else 'OFF'})")

    Xtr = np.concatenate([feats_train(ptr_v, N_TRAIN_PER_CLASS, base_w=1.0, is_neg=False),
                          feats_train(ntr_v, N_TRAIN_PER_CLASS, base_w=1.0, is_neg=True)])
    ytr = np.array([1]*N_TRAIN_PER_CLASS + [0]*N_TRAIN_PER_CLASS, np.int64)

    Xva = np.concatenate([feats_real(pva), feats_real(nva)])
    yva = np.array([1]*len(pva) + [0]*len(nva), np.int64)
    Xte = np.concatenate([feats_real(pte), feats_real(nte)])
    yte = np.array([1]*len(pte) + [0]*len(nte), np.int64)

    # embaralha treino
    idx = np_rng.permutation(len(Xtr)); Xtr, ytr = Xtr[idx], ytr[idx]

    va_files = [str(f.relative_to(PROJ)) for f in pva] + [str(f.relative_to(PROJ)) for f in nva]
    te_files = [str(f.relative_to(PROJ)) for f in pte] + [str(f.relative_to(PROJ)) for f in nte]
    out = PROJ / "metadata" / "dataset.npz"
    np.savez_compressed(out, Xtr=Xtr, ytr=ytr, Xva=Xva, yva=yva, Xte=Xte, yte=yte,
                        va_files=np.array(va_files), te_files=np.array(te_files))
    print("shapes:", Xtr.shape, Xva.shape, Xte.shape)
    print("salvo:", out.relative_to(PROJ))

if __name__ == "__main__":
    main()
