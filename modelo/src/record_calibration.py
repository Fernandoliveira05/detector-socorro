#!/usr/bin/env python3
"""
Grava amostras de calibração pelo SEU microfone.

Uso:
  python record_calibration.py socorro 20 normal      # "socorro" em tom normal
  python record_calibration.py socorro 20 sussurro    # "socorro" sussurrado
  python record_calibration.py socorro 20 grito        # "socorro" gritado
  python record_calibration.py negativo 20 normal     # outras palavras, tom normal/baixo

3º arg (tom) é opcional e serve só p/ instrução + nome do arquivo.
Positivos -> dataset/positives/ | Negativos -> dataset/negatives/mic_user/
Depois rode:  bash projeto/src/retrain.sh
"""
import sys, time
from pathlib import Path
import numpy as np, soundfile as sf, sounddevice as sd

PROJ = Path(__file__).resolve().parents[1]
SR = 16000
DUR = 1.4

def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("socorro", "negativo"):
        print(__doc__); sys.exit(1)
    classe = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    tom = sys.argv[3] if len(sys.argv) > 3 else "qualquer"

    if classe == "socorro":
        out = PROJ / "dataset" / "positives"; prefix = f"mic_socorro_{tom}"
        instr = f"diga 'SOCORRO' em tom: {tom.upper()}"
    else:
        out = PROJ / "dataset" / "negatives" / "mic_user"; prefix = f"mic_neg_{tom}"
        instr = f"diga OUTRA palavra (NÃO socorro) em tom: {tom.upper()}"
    out.mkdir(parents=True, exist_ok=True)

    print(f"\nGravando {n} amostras de '{classe}' ({tom}). Cada uma ~{DUR}s.")
    print(f"Quando aparecer 'JÁ!', {instr}.\n")
    input("Enter pra começar...")
    for i in range(n):
        for c in (3, 2, 1):
            print(f"\r  amostra {i+1}/{n} em {c}...", end="", flush=True); time.sleep(0.7)
        print("\r  >>> JÁ!                       ", flush=True)
        rec = sd.rec(int(DUR*SR), samplerate=SR, channels=1, dtype="float32")
        sd.wait()
        y = rec[:, 0]
        # normaliza p/ o modelo focar na FORMA/fonética (invariante a volume)
        y = y / (np.max(np.abs(y)) + 1e-9) * 0.95
        sf.write(out / f"{prefix}_{int(time.time()*1000)}.wav", y, SR)
        time.sleep(0.3)
    print(f"\nOK! {n} amostras em {out.relative_to(PROJ)}")

if __name__ == "__main__":
    main()
