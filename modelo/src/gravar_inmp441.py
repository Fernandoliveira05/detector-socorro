#!/usr/bin/env python3
"""
Grava o áudio que o INMP441 transmite pela serial (firmware com DUMP_AUDIO=1).
Salva um WAV 16kHz mono em _work/inmp441/.

Uso:  python gravar_inmp441.py <nome> <segundos>
Ex.:  python gravar_inmp441.py socorro 20
"""
import sys, time, glob
from pathlib import Path
import numpy as np, soundfile as sf, serial

SR = 16000
nome = sys.argv[1] if len(sys.argv) > 1 else "captura"
dur  = float(sys.argv[2]) if len(sys.argv) > 2 else 15.0
out = Path(__file__).resolve().parents[2] / "_work" / "inmp441"; out.mkdir(parents=True, exist_ok=True)

port = (glob.glob("/dev/cu.usbserial*") + glob.glob("/dev/cu.usbmodem*"))[0]
ser = serial.Serial(port, 921600, timeout=0.2)
time.sleep(1.5); ser.reset_input_buffer()          # descarta lixo do boot
print(f"Gravando {dur:.0f}s de '{nome}' — FALE AGORA...")
buf = bytearray(); t0 = time.time()
while time.time() - t0 < dur:
    buf += ser.read(4096)
ser.close()
y = np.frombuffer(bytes(buf[: len(buf)//2*2]), dtype='<i2').astype(np.float32) / 32768.0
path = out / f"{nome}_{int(time.time())}.wav"
sf.write(path, y, SR)
print(f"salvo: {path}  ({len(y)/SR:.1f}s, rms={np.sqrt(np.mean(y**2)):.3f})")
