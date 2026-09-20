#!/usr/bin/env python3
"""
Demo AO VIVO: detecta "socorro" pelo microfone em tempo real.
Espelha a lógica do ESP32 (janela deslizante + suavização temporal).

Uso:  python demo_mic.py
Fale/gRite "socorro". Ctrl+C p/ sair.
"""
import sys, json, time, datetime
from pathlib import Path
import numpy as np, onnxruntime as ort, sounddevice as sd, soundfile as sf
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import SR, CLIP_LEN, mfcc

PROJ = Path(__file__).resolve().parents[1]
HOP = CLIP_LEN // 16                   # ~62ms: amostragem densa (buffer avança rápido)
CONSEC = 6                             # ~375ms sustentados: socorro passa, blip de fala não
COOLDOWN = 1.5                         # s entre alertas

# Pasta SEPARADA (fora do dataset de treino) p/ você revisar os disparos
# antes de aprovar como dado. Cada arquivo traz data/hora e a probabilidade.
DET_DIR = PROJ.parent / "audios" / "deteccoes"
DET_DIR.mkdir(parents=True, exist_ok=True)

sess = ort.InferenceSession(str(PROJ/"models"/"socorro.onnx"),
                            providers=["CPUExecutionProvider"])
IN = sess.get_inputs()[0].name
# norm global + label smoothing: probabilidades calibradas -> threshold 0.55 + debounce 6.
# ajuste ao vivo:  python demo_mic.py 0.45 (mais sensível) | 0.65 (mais rígido)
THR = 0.55
if len(sys.argv) > 1:
    THR = float(sys.argv[1])

ring = np.zeros(CLIP_LEN, dtype=np.float32)
# gate baixo: só barra silêncio absoluto/DC. Sussurro tem energia ~ruído,
# então a discriminação fica com o modelo (treinado c/ ruído real do mic).
RMS_GATE = 0.005

def infer():
    rms = float(np.sqrt(np.mean(ring ** 2)))
    if rms < RMS_GATE:                    # gate de energia (usa a feature RMS do enunciado)
        return 0.0
    x = mfcc(ring)[None, ..., None].astype(np.float32)
    return float(sess.run(None, {IN: x})[0][0, 1])

def main():
    print(f"🎙  Ouvindo... (threshold={THR:.2f}) — grite 'SOCORRO'. Ctrl+C p/ sair.\n")
    consec = 0; last_alert = 0.0
    def cb(indata, frames, t, status):
        global ring
        ring = np.roll(ring, -frames)
        ring[-frames:] = indata[:, 0]
    with sd.InputStream(channels=1, samplerate=SR, blocksize=HOP, callback=cb):
        while True:
            time.sleep(HOP / SR)
            p = infer()                       # probabilidade INSTANTÂNEA da janela
            bar = "█" * int(p * 30)
            consec = consec + 1 if p >= THR else 0
            now = time.time()
            if consec >= CONSEC and (now - last_alert) > COOLDOWN:
                # salva o áudio (1s) que disparou, p/ revisão e treino futuro
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                fname = DET_DIR / f"det_{ts}_p{int(p*100):03d}.wav"
                sf.write(fname, ring.copy(), SR)
                print(f"\r🚨 SOCORRO DETECTADO!  (p={p:.2f})  salvo: {fname.name}      ")
                last_alert = now; consec = 0
            else:
                print(f"\rp={p:0.2f} |{bar:<30}|", end="", flush=True)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nencerrado.")
