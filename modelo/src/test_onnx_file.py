#!/usr/bin/env python3
"""
Testa o modelo socorro.onnx em arquivos de áudio (qualquer formato).
Desliza uma janela de 1s (hop 0.5s), roda o ONNX e reporta detecções.

Uso:
  python test_onnx_file.py <audio1> [audio2 ...]
  python test_onnx_file.py            # usa alguns exemplos da pasta
"""
import sys, json, subprocess, tempfile
from pathlib import Path
import numpy as np, onnxruntime as ort
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import SR, CLIP_LEN, mfcc

PROJ = Path(__file__).resolve().parents[1]
ROOT = PROJ.parent
HOP = CLIP_LEN // 2

sess = ort.InferenceSession(str(PROJ/"models"/"socorro.onnx"),
                            providers=["CPUExecutionProvider"])
IN = sess.get_inputs()[0].name
THR = json.load(open(PROJ/"models"/"metrics.json")).get("thr_balanced", 0.5)

def load_any(path):
    """Converte qualquer áudio p/ float32 16k mono via ffmpeg."""
    with tempfile.NamedTemporaryFile(suffix=".raw", delete=False) as tmp:
        subprocess.run(["ffmpeg","-v","error","-y","-i",str(path),
                        "-ar",str(SR),"-ac","1","-f","f32le",tmp.name], check=True)
        y = np.fromfile(tmp.name, dtype=np.float32)
    Path(tmp.name).unlink(missing_ok=True)
    return y

def scan(path):
    y = load_any(path)
    if len(y) < CLIP_LEN:
        y = np.pad(y, (0, CLIP_LEN-len(y)))
    probs = []
    for a in range(0, len(y)-CLIP_LEN+1, HOP):
        seg = y[a:a+CLIP_LEN]
        x = mfcc(seg)[None, ..., None].astype(np.float32)
        p = float(sess.run(None, {IN: x})[0][0, 1])
        probs.append((a/SR, p))
    return probs

def main():
    args = sys.argv[1:]
    if not args:
        args = [str(ROOT/"WhatsApp Ptt 2026-09-16 at 00.17.58.ogg"),
                str(ROOT/"Rua MMDC 5.m4a.mp4"),
                str(ROOT/"Nova Gravação.m4a.mp4"),
                str(ROOT/"Engenharia Civil e Ambiental 8.m4a.mp4")]
    print(f"threshold balanceado = {THR:.3f}\n")
    for a in args:
        probs = scan(a)
        if not probs:
            print(f"{Path(a).name}: (vazio)"); continue
        pmax = max(p for _, p in probs)
        hits = [f"{t:.1f}s(p={p:.2f})" for t, p in probs if p >= THR]
        verdict = "🚨 SOCORRO" if pmax >= THR else "— nada"
        print(f"{verdict:12s} pmax={pmax:.2f}  {Path(a).name}")
        if hits:
            print(f"             janelas: {', '.join(hits[:8])}")

if __name__ == "__main__":
    main()
