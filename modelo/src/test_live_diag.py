#!/usr/bin/env python3
"""
Diagnóstico AO VIVO: grava você dizendo 'socorro' em 3 tons, mostra a
probabilidade que o modelo dá pra cada um (e a RMS/gate), e salva os áudios
em _work/live_test/ pra análise.

Uso:  python projeto/src/test_live_diag.py
"""
import sys, time
from pathlib import Path
import numpy as np, soundfile as sf, sounddevice as sd, onnxruntime as ort
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import SR, CLIP_LEN, fix_length, mfcc

PROJ = Path(__file__).resolve().parents[1]
OUT = PROJ.parent / "_work" / "live_test"; OUT.mkdir(parents=True, exist_ok=True)
sess = ort.InferenceSession(str(PROJ/"models"/"socorro.onnx"), providers=["CPUExecutionProvider"])
IN = sess.get_inputs()[0].name
DUR = 1.6

def prob(y):
    return float(sess.run(None, {IN: mfcc(fix_length(y))[None,...,None].astype(np.float32)})[0][0,1])

def main():
    print("Diagnóstico ao vivo. Vou pedir 'socorro' em 3 tons.\n")
    for tom in ["GRITADO", "tom NORMAL", "SUSSURRADO"]:
        input(f"Enter e diga 'socorro' {tom}...")
        for c in (3,2,1):
            print(f"\r  em {c}...", end="", flush=True); time.sleep(0.6)
        print("\r  >>> FALE!            ")
        rec = sd.rec(int(DUR*SR), samplerate=SR, channels=1, dtype="float32"); sd.wait()
        y = rec[:,0]
        rms = float(np.sqrt(np.mean(y**2)))
        p = prob(y)
        sf.write(OUT / f"live_{tom.split()[-1].lower()}.wav", y, SR)
        print(f"     => p_socorro = {p:.2f}   rms = {rms:.4f}   (peak={np.max(np.abs(y)):.3f})\n")
    print("Áudios salvos em _work/live_test/  (me mande os valores de p que apareceram)")

if __name__ == "__main__":
    main()
