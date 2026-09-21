"""
Código de teste — simula anomalias e mede performance.

Faz duas coisas:
  1) LATÊNCIA: mede quanto tempo o modelo leva por inferência (não precisa de áudio).
  2) ACURÁCIA: se você apontar para a pasta de áudios, roda o modelo em "socorro"
     (a anomalia) e em "não-socorro" e reporta precisão / recall / acurácia.

Uso:
  python testar.py                 # só a latência (rápido, sem áudio)
  python testar.py ../audios       # latência + acurácia (pasta com subpastas
                                   #   socorro/ e nao_socorro/, ex.: baixada do Drive)
"""
import sys, time, json, glob
from pathlib import Path
import numpy as np, onnxruntime as ort
from common import SR, CLIP_LEN, N_FRAMES, N_MFCC, fix_length, mfcc

M = Path("modelos")
sess = ort.InferenceSession(str(M/"socorro.onnx"), providers=["CPUExecutionProvider"])
IN = sess.get_inputs()[0].name
THR = json.load(open(M/"metrics.json")).get("frozen", {}).get("threshold", 0.55)

def prob(feat):
    return float(sess.run(None, {IN: feat[None, ..., None].astype(np.float32)})[0][0, 1])

# ---------- 1) LATÊNCIA ----------
x = np.random.randn(N_FRAMES, N_MFCC).astype(np.float32)      # entrada sintética
for _ in range(5): prob(x)                                    # aquece
N = 200; t0 = time.perf_counter()
for _ in range(N): prob(x)
ms = (time.perf_counter() - t0) / N * 1000
print("=== LATÊNCIA (inferência) ===")
print(f"  {ms:.2f} ms por inferência  ->  ~{1000/ms:.0f} janelas/s")

# ---------- 2) ACURÁCIA (se houver áudios) ----------
if len(sys.argv) > 1:
    import librosa
    base = Path(sys.argv[1])
    soc = glob.glob(str(base/"socorro"/"*"))
    neg = glob.glob(str(base/"nao_socorro"/"*"))
    if not soc and not neg:
        print("\n(sem subpastas socorro/ e nao_socorro/ em", base, "- pulei a acurácia)")
    else:
        def detecta(f):
            y = fix_length(librosa.load(f, sr=SR, mono=True)[0])
            return prob(mfcc(y)) >= THR
        tp = sum(detecta(f) for f in soc);  fn = len(soc) - tp     # anomalias
        fp = sum(detecta(f) for f in neg);  tn = len(neg) - fp     # não-anomalias
        prec = tp / (tp + fp + 1e-9); rec = tp / (tp + fn + 1e-9)
        acc = (tp + tn) / (len(soc) + len(neg) + 1e-9)
        print(f"\n=== ACURÁCIA (threshold={THR}) ===")
        print(f"  socorros (anomalias): {len(soc)}  |  não-socorro: {len(neg)}")
        print(f"  detectados certos: TP={tp}  FN={fn}  |  falsos+: FP={fp}  TN={tn}")
        print(f"  precisão={prec:.3f}  recall={rec:.3f}  acurácia={acc:.3f}")
else:
    print("\n(rode 'python testar.py ../audios' para medir a acurácia com os áudios)")
