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

WARMUP = 3.0                                        # descarta o transiente inicial do INMP441 (DC settling)
port = (glob.glob("/dev/cu.usbserial*") + glob.glob("/dev/cu.usbmodem*"))[0]
ser = serial.Serial(port, 921600, timeout=0.2)
time.sleep(1.5); ser.reset_input_buffer()          # descarta lixo do boot
print(f"Aquecendo o mic ({WARMUP:.0f}s, NÃO fale ainda)...")
tw = time.time()
while time.time() - tw < WARMUP:                    # lê e joga fora o começo (estoura no início)
    ser.read(4096)
ser.reset_input_buffer()
print(f"Gravando {dur:.0f}s de '{nome}' — FALE AGORA...")
buf = bytearray(); t0 = time.time()
while time.time() - t0 < dur:
    buf += ser.read(4096)
ser.close()
y = np.frombuffer(bytes(buf[: len(buf)//2*2]), dtype='<i2').astype(np.float32) / 32768.0
y = y[int(0.3*SR):]                                 # trim extra de 0.3s por segurança
got = len(y) / SR
if got < dur * 0.5:                                  # veio muito menos áudio que o pedido
    print(f"⚠️  ATENÇÃO: só chegaram {got:.1f}s de {dur:.0f}s pedidos.")
    print("   O ESP provavelmente NÃO está com DUMP_AUDIO=1 gravado. Reflashe o firmware de captura e tente de novo.")
rms  = float(np.sqrt(np.mean(y**2))) if len(y) else 0.0
peak = float(np.max(np.abs(y))) if len(y) else 0.0
clip = float(np.mean(np.abs(y) > 0.95)) * 100 if len(y) else 0.0   # limiar mais sensível
path = out / f"{nome}_{int(time.time())}.wav"
sf.write(path, y, SR)
print(f"salvo: {path}  ({got:.1f}s, rms={rms:.3f}, pico={peak:.2f}, estouro={clip:.1f}%)")
if rms > 0.40 or clip > 1.0:
    print("   ⚠️  QUENTE DEMAIS (distorce). Aumente GAIN_SHIFT no config.h (+1), reflashe e repita.")
elif rms < 0.03:
    print("   ⚠️  baixo demais. Fale mais perto ou diminua GAIN_SHIFT (-1).")
else:
    print("   ✅ nível bom (rms ~0.05–0.35), áudio limpo.")
