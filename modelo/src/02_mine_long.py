#!/usr/bin/env python3
"""
Etapa 2: minera os áudios LONGOS (dataset/long_mined/src/*.wav).
Usa timestamps por palavra do whisper.cpp para:
  - cortar janelas de ~1s em volta de palavras foneticamente "socorro" -> POSITIVOS extras
  - cortar janelas de ~1s em volta de fala não-socorro -> NEGATIVOS (fala PT)
"""
import json, re, subprocess, unicodedata
from pathlib import Path
import numpy as np, soundfile as sf, librosa

PROJ = Path(__file__).resolve().parents[1]
ROOT = PROJ.parent
MODEL = ROOT / "_models" / "ggml-small.bin"
SRC   = PROJ / "dataset" / "long_mined" / "src"
POS   = PROJ / "dataset" / "positives"
NEGPT = PROJ / "dataset" / "negatives" / "pt_speech"
NEGPT.mkdir(parents=True, exist_ok=True)
SR = 16000
WIN = 1.0            # duração da janela extraída (s)
NEG_EVERY = 3        # amostra 1 a cada N palavras não-socorro

def deacc(s):
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn").lower()

SOC = re.compile(r"soc|sacarr|corro|corra|couro|curro|cor{2}")

def words_of(wav: Path):
    of = str(PROJ / "_wmine")
    subprocess.run(["whisper-cli", "-m", str(MODEL), "-l", "pt",
                    "-ml", "1", "-sow", "-oj", "-of", of, str(wav)],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    d = json.load(open(of + ".json", encoding="utf-8"))
    out = []
    for s in d["transcription"]:
        t = s["text"].strip()
        if not t:
            continue
        out.append((s["offsets"]["from"]/1000.0, s["offsets"]["to"]/1000.0, t))
    return out

def cut(y, center, dst):
    half = WIN / 2
    a = int(max(0, center - half) * SR)
    b = a + int(WIN * SR)
    seg = y[a:b]
    if len(seg) < int(WIN * SR):
        seg = np.pad(seg, (0, int(WIN * SR) - len(seg)))
    peak = np.max(np.abs(seg)) or 1.0
    sf.write(dst, (seg / peak * 0.95).astype(np.float32), SR)

def main():
    npos = nneg = 0
    for wav in sorted(SRC.glob("*.wav")):
        y, _ = librosa.load(wav, sr=SR, mono=True)
        words = words_of(wav)
        stem = wav.stem
        nonsoc = 0
        for (t0, t1, txt) in words:
            c = (t0 + t1) / 2
            if SOC.search(deacc(txt)):
                cut(y, c, POS / f"mined_{stem}_{int(c*1000)}.wav"); npos += 1
            else:
                nonsoc += 1
                if nonsoc % NEG_EVERY == 0 and len(deacc(txt)) >= 2:
                    cut(y, c, NEGPT / f"mined_{stem}_{int(c*1000)}.wav"); nneg += 1
        print(f"{stem[:40]:40s}  +{sum(1 for w in words if SOC.search(deacc(w[2])))} soc")
    print(f"\nPOSITIVOS minerados: {npos}")
    print(f"NEGATIVOS (fala PT) minerados: {nneg}")

if __name__ == "__main__":
    main()
