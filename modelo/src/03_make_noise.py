#!/usr/bin/env python3
"""
Etapa 3: gera NEGATIVOS sintéticos de ruído e silêncio (1s, 16kHz).
Tipos: silêncio (quase), ruído branco/rosa/marrom, tons (hum 60Hz, apitos),
misturas em vários níveis. Simula o que o INMP441 capta sem ninguém gritando.
"""
import numpy as np, soundfile as sf
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
OUT  = PROJ / "dataset" / "negatives" / "noise"
OUT.mkdir(parents=True, exist_ok=True)
SR, WIN = 16000, 1.0
N = int(SR * WIN)
rng = np.random.default_rng(42)

def norm(x, level):
    p = np.max(np.abs(x)) or 1.0
    return (x / p * level).astype(np.float32)

def white():   return rng.standard_normal(N)
def pink():
    # ruído rosa via filtro simples (integração parcial)
    w = rng.standard_normal(N); b = np.zeros(N); a = 0.0
    for i in range(N):
        a = 0.98 * a + 0.02 * w[i]; b[i] = a + w[i] * 0.1
    return b
def brown():
    return np.cumsum(rng.standard_normal(N))
def tone(f):
    t = np.arange(N)/SR; return np.sin(2*np.pi*f*t)

count = 0
def save(x, tag, level):
    global count
    sf.write(OUT / f"noise_{tag}_{count:04d}.wav", norm(x, level), SR); count += 1

for _ in range(60):
    save(white(), "white", rng.uniform(0.02, 0.6))
for _ in range(40):
    save(pink(), "pink", rng.uniform(0.05, 0.7))
for _ in range(40):
    save(brown(), "brown", rng.uniform(0.1, 0.8))
for _ in range(40):
    save(tone(rng.uniform(50, 400)) + 0.2*white(), "hum", rng.uniform(0.05, 0.5))
for _ in range(30):
    save(tone(rng.uniform(1000, 4000)) + 0.1*white(), "whistle", rng.uniform(0.05, 0.4))
# silêncio quase absoluto (ruído de fundo baixíssimo)
for _ in range(60):
    save(white(), "silence", rng.uniform(0.001, 0.02))

print(f"NEGATIVOS de ruído/silêncio gerados: {count}")
