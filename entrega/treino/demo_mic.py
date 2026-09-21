"""
Demo AO VIVO no PC — mesma lógica do firmware (janela deslizante + debounce).
Detecta "socorro" pelo microfone do computador.

Uso:  python demo_mic.py          (threshold 0.55)
      python demo_mic.py 0.45     (mais sensível)
"""
import sys, time, json
from pathlib import Path
import numpy as np, onnxruntime as ort, sounddevice as sd
from common import SR, CLIP_LEN, mfcc

M = Path("modelos")
sess = ort.InferenceSession(str(M/"socorro.onnx"), providers=["CPUExecutionProvider"])
IN = sess.get_inputs()[0].name
THR = float(sys.argv[1]) if len(sys.argv) > 1 else \
      json.load(open(M/"metrics.json")).get("frozen", {}).get("threshold", 0.55)
HOP = CLIP_LEN // 16          # ~62 ms
CONSEC, GATE = 6, 0.005
ring = np.zeros(CLIP_LEN, dtype=np.float32)

def infer():
    if np.sqrt(np.mean(ring**2)) < GATE: return 0.0     # gate de energia (RMS)
    x = mfcc(ring)[None, ..., None].astype(np.float32)
    return float(sess.run(None, {IN: x})[0][0, 1])

def main():
    print(f"🎙  Ouvindo (threshold={THR:.2f}) — grite 'SOCORRO'. Ctrl+C p/ sair.\n")
    consec = 0; last = 0.0
    def cb(indata, frames, t, s):
        global ring
        ring = np.roll(ring, -frames); ring[-frames:] = indata[:, 0]
    with sd.InputStream(channels=1, samplerate=SR, blocksize=HOP, callback=cb):
        while True:
            time.sleep(HOP / SR)
            p = infer(); consec = consec + 1 if p >= THR else 0
            if consec >= CONSEC and time.time() - last > 1.5:
                print(f"\r🚨 SOCORRO DETECTADO!  (p={p:.2f})                      ")
                last = time.time(); consec = 0
            else:
                print(f"\rp={p:0.2f} |{'█'*int(p*30):<30}|", end="", flush=True)

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: print("\nencerrado.")
