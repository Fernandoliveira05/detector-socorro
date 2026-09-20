#!/usr/bin/env python3
"""
Etapa 12: fatia gravações de CONVERSA real (_work/conversa*.wav) em janelas de 1s
-> negativos in-domain de fala contínua (dataset/negatives/conversation/).
Resolve o falso positivo em "pessoas conversando sem dizer socorro".
"""
import sys
from pathlib import Path
import numpy as np, soundfile as sf, librosa
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import SR, CLIP_LEN

PROJ = Path(__file__).resolve().parents[1]
ROOT = PROJ.parent
OUT = PROJ / "dataset" / "negatives" / "conversation"
OUT.mkdir(parents=True, exist_ok=True)
GATE = 0.005
hop = CLIP_LEN // 2
n = 0
for s in sorted((ROOT/"_work").glob("conversa*.wav")):
    y = librosa.load(s, sr=SR, mono=True)[0]
    for a in range(0, max(1, len(y)-CLIP_LEN+1), hop):
        seg = y[a:a+CLIP_LEN]
        if len(seg) < CLIP_LEN: seg = np.pad(seg, (0, CLIP_LEN-len(seg)))
        if np.sqrt(np.mean(seg**2)) < GATE:      # pula silêncio (não é fala)
            continue
        sf.write(OUT / f"conv_{n:04d}.wav", seg.astype(np.float32), SR); n += 1
print(f"negativos de conversa gerados: {n}")
