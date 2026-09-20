#!/usr/bin/env python3
"""
Etapa 9: ingere os áudios gravados NO PC (mesmo microfone do demo).
  "Audios do PC"          -> dataset/positives/pc_*.wav        (socorro)
  "Audios Negativos PC"   -> dataset/negatives/pc_neg/*.wav    (não-socorro, entonação de socorro)
Transcreve cada um p/ conferência.
"""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROJ = Path(__file__).resolve().parents[1]
MODEL = ROOT / "_models" / "ggml-small.bin"
SR = 16000

JOBS = [
    (ROOT / "audios" / "pc_positivos",  PROJ / "dataset" / "positives",            "pc"),
    (ROOT / "audios" / "pc_negativos",  PROJ / "dataset" / "negatives" / "pc_neg", "pcneg"),
]

def to_wav(src, dst):
    subprocess.run(["ffmpeg","-v","error","-y","-i",str(src),
                    "-ar",str(SR),"-ac","1","-sample_fmt","s16",str(dst)], check=True)

def transcribe(wav):
    subprocess.run(["whisper-cli","-m",str(MODEL),"-l","pt","-nt","-np",
                    "-of", str(PROJ/"_pctx"), "-otxt", str(wav)],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t = Path(str(PROJ/"_pctx")+".txt")
    return t.read_text(encoding="utf-8").strip().replace("\n"," ") if t.exists() else ""

for src_dir, out_dir, prefix in JOBS:
    out_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(src_dir.glob("*.m4a")) + sorted(src_dir.glob("*.mp4")) + \
            sorted(src_dir.glob("*.wav")) + sorted(src_dir.glob("*.ogg"))
    print(f"\n=== {src_dir.name}  ({len(files)} arq) -> {out_dir.relative_to(PROJ)} ===")
    for i, f in enumerate(files):
        dst = out_dir / f"{prefix}_{i:02d}.wav"
        to_wav(f, dst)
        print(f"  {dst.name}: {transcribe(dst)!r}")
