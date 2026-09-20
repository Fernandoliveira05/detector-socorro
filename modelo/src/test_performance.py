#!/usr/bin/env python3
"""
Script de teste/performance (entregável da ponderada).
- Simula anomalias: roda o modelo em positivos (socorro) e negativos.
- Mede: acurácia/precisão/recall no ponto de operação congelado e a
  LATÊNCIA de inferência (proxy PC do que roda no ESP32).

Uso:  python projeto/src/test_performance.py
"""
import sys, time, json, random
from pathlib import Path
import numpy as np, onnxruntime as ort, librosa
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import SR, fix_length, mfcc

PROJ = Path(__file__).resolve().parents[1]
sess = ort.InferenceSession(str(PROJ/"models"/"socorro.onnx"), providers=["CPUExecutionProvider"])
IN = sess.get_inputs()[0].name
THR = json.load(open(PROJ/"models"/"metrics.json")).get("frozen", {}).get("threshold", 0.85)
random.seed(0)

def prob(y):
    x = mfcc(fix_length(y))[None, ..., None].astype(np.float32)
    return float(sess.run(None, {IN: x})[0][0, 1])

def sample(glob, k=120):
    fs = sorted(PROJ.glob(glob))
    return random.sample(fs, min(k, len(fs)))

def main():
    pos = sample("dataset/positives/*.wav")
    neg = (sample("dataset/negatives/mic_noise/*.wav", 60)
           + sample("dataset/negatives/pc_neg/*.wav", 40)
           + sample("dataset/negatives/conversation/*.wav", 60)
           + sample("dataset/negatives/pt_speech/*.wav", 60))

    # --- desempenho de classificação ---
    tp = sum(prob(librosa.load(f, sr=SR, mono=True)[0]) >= THR for f in pos)
    fp = sum(prob(librosa.load(f, sr=SR, mono=True)[0]) >= THR for f in neg)
    fn = len(pos) - tp; tn = len(neg) - fp
    prec = tp / (tp + fp + 1e-9); rec = tp / (tp + fn + 1e-9)
    print(f"=== DESEMPENHO (threshold={THR}) ===")
    print(f"  positivos: {len(pos)}  | negativos: {len(neg)}")
    print(f"  TP={tp} FP={fp} FN={fn} TN={tn}")
    print(f"  precisão={prec:.3f}  recall={rec:.3f}  "
          f"acurácia={(tp+tn)/(len(pos)+len(neg)):.3f}")

    # --- latência de inferência ---
    y = librosa.load(pos[0], sr=SR, mono=True)[0]
    x = mfcc(fix_length(y))[None, ..., None].astype(np.float32)
    for _ in range(5): sess.run(None, {IN: x})       # warm-up
    N = 200; t0 = time.perf_counter()
    for _ in range(N): sess.run(None, {IN: x})
    dt = (time.perf_counter() - t0) / N * 1000
    print(f"\n=== LATÊNCIA (inferência ONNX, PC) ===")
    print(f"  {dt:.2f} ms/janela  ->  ~{1000/dt:.0f} inferências/s")
    print(f"  (no ESP32 a inferência TFLM int8 é o gargalo; medida via Serial no firmware)")

if __name__ == "__main__":
    main()
