#!/usr/bin/env python3
"""
Etapa 13 (aumento por VARIAÇÃO DE VOZ):
Cria 3 versões de cada áudio de voz, simulando pessoas/entonações diferentes:
  V1 = voz mais grave  (pitch e formantes ↓)
  V2 = voz mais aguda  (pitch e formantes ↑)  -> robustez a vozes femininas
  V3 = fala mais arrastada (mesma voz, ritmo/entonação diferente)

Método: resample (desloca pitch E formantes juntos, como corpos de tamanhos
diferentes) + time-stretch p/ restaurar a duração. Só librosa — rápido e estável
(o parselmouth/Praat travava em alguns clipes).

Aplicado a POSITIVOS e NEGATIVOS de voz (SIMETRIA — o modelo aprende a palavra,
não a transformação). As variações vão p/ pastas *_variants e, no build, entram
SÓ NO TREINO (nunca em validação/teste) -> sem vazamento.
Nomes: <stem>__vN.wav (o build acha as variações pelo stem do original).
"""
import sys, random
from pathlib import Path
import numpy as np, soundfile as sf, librosa
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import SR, CLIP_LEN

PROJ = Path(__file__).resolve().parents[1]
DS = PROJ / "dataset"
random.seed(11)

POS_SRC = DS / "positives";              POS_OUT = DS / "positives_variants"
NEG_SUBDIRS = ["from_recordings", "pt_speech", "other_words", "pc_neg",
               "mic_user", "loud_speech", "conversation"]
NEG_OUT = DS / "negatives_variants"
CAP_POR_SUBDIR = 120

def joint_shift(y, r):
    """Desloca pitch+formantes por fator r (r>1 agudo, r<1 grave), mantendo duração."""
    if abs(r - 1.0) < 1e-3:
        return y.astype(np.float32)
    sped = librosa.resample(y, orig_sr=SR, target_sr=int(SR / r))   # pitch+formante ×r
    out = librosa.effects.time_stretch(sped, rate=1.0 / r)          # restaura duração
    return out.astype(np.float32)

def variar(y):
    outs = []
    try: outs.append(("v1", joint_shift(y, 0.88)))                  # grave
    except Exception: pass
    try: outs.append(("v2", joint_shift(y, 1.12)))                  # aguda
    except Exception: pass
    try: outs.append(("v3", librosa.effects.time_stretch(y, rate=0.85).astype(np.float32)))  # arrastada
    except Exception: pass
    res = []
    for tag, v in outs:
        m = np.max(np.abs(v)) or 1.0
        res.append((tag, (v / m * 0.95).astype(np.float32)))
    return res

def processar(files, outdir):
    outdir.mkdir(parents=True, exist_ok=True)
    n = 0
    for f in files:
        try:
            y = librosa.load(f, sr=SR, mono=True)[0]
        except Exception:
            continue
        if len(y) < SR // 4:                     # pula clipes muito curtos (<0.25s)
            continue
        for tag, v in variar(y):
            sf.write(outdir / f"{f.stem}__{tag}.wav", v, SR); n += 1
    return n

def main():
    npos = processar(sorted(POS_SRC.glob("*.wav")), POS_OUT)
    print(f"variações de POSITIVOS: {npos}")
    negfiles = []
    for sub in NEG_SUBDIRS:
        fs = sorted((DS / "negatives" / sub).glob("*.wav")); random.shuffle(fs)
        negfiles += fs[:CAP_POR_SUBDIR]
    nneg = processar(negfiles, NEG_OUT)
    print(f"variações de NEGATIVOS: {nneg}")

if __name__ == "__main__":
    main()
