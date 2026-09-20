#!/usr/bin/env python3
"""
Etapa 10: fatia gravações de ruído REAL do microfone (_work/ambiente*.wav)
em janelas de 1s -> negativos in-domain (dataset/negatives/mic_noise/).
Também cria variantes com ganho pra cobrir ruído mais forte.
"""
import sys
from pathlib import Path
import numpy as np, soundfile as sf, librosa
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import SR, CLIP_LEN

PROJ = Path(__file__).resolve().parents[1]
ROOT = PROJ.parent
OUT = PROJ / "dataset" / "negatives" / "mic_noise"
OUT.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(3)

srcs = sorted((ROOT/"_work").glob("ambiente*.wav"))
hop = CLIP_LEN // 2
n = 0
for s in srcs:
    y = librosa.load(s, sr=SR, mono=True)[0]
    for a in range(0, max(1, len(y)-CLIP_LEN+1), hop):
        seg = y[a:a+CLIP_LEN]
        if len(seg) < CLIP_LEN:
            seg = np.pad(seg, (0, CLIP_LEN-len(seg)))
        sf.write(OUT / f"micnoise_{n:04d}.wav", seg.astype(np.float32), SR); n += 1
        # variante com ganho (ruído mais alto) p/ robustez
        g = seg * rng.uniform(1.5, 4.0)
        g = np.clip(g, -1, 1)
        sf.write(OUT / f"micnoise_{n:04d}.wav", g.astype(np.float32), SR); n += 1

print(f"negativos de ruído real do mic gerados: {n} (de {len(srcs)} gravações)")
