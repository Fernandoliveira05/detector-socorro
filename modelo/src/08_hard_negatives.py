#!/usr/bin/env python3
"""
Etapa 8: gera NEGATIVOS DIFÍCEIS = outras palavras/fala em VOZ ERGUIDA.
Objetivo: ensinar o modelo que "voz alta" sozinha NÃO é socorro — só a palavra é.
Cria variantes com pitch acima, ganho e leve compressão (som de grito realista),
a partir dos negativos de fala existentes.
"""
import sys, random
from pathlib import Path
import numpy as np, soundfile as sf, librosa
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import SR, CLIP_LEN, fix_length

PROJ = Path(__file__).resolve().parents[1]
NEG  = PROJ / "dataset" / "negatives"
OUT  = NEG / "loud_speech"
OUT.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(7); random.seed(7)

def raise_voice(y):
    y = fix_length(y)
    # pitch acima (grito costuma subir 2-5 semitons)
    y = librosa.effects.pitch_shift(y=y, sr=SR, n_steps=rng.uniform(2, 5))
    # leve compressão + ganho (tira dinâmica, deixa "forte" sem distorcer)
    y = np.sign(y) * np.power(np.abs(y) + 1e-6, 0.7)
    y = y / (np.max(np.abs(y)) + 1e-9) * rng.uniform(0.85, 1.0)
    return fix_length(y).astype(np.float32)

src = (sorted((NEG/"other_words").glob("*.wav")) +
       sorted((NEG/"pt_speech").glob("*.wav")))
random.shuffle(src)
n = 0
for f in src[:500]:
    try:
        y = librosa.load(f, sr=SR, mono=True)[0]
        sf.write(OUT / f"loud_{f.stem}.wav", raise_voice(y), SR); n += 1
    except Exception:
        pass
print(f"negativos difíceis (voz erguida) gerados: {n}")
