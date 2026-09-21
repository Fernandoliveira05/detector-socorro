"""
Prepara os dados: converte os áudios brutos em WAV 16 kHz mono e monta o
conjunto de positivos ("socorro") e negativos (tudo que NÃO é socorro).

Os áudios brutos ficam no Drive (ver README). Aponte AUDIO_DIR para a pasta
baixada, com subpastas: socorro/ e nao_socorro/.

Gera também negativos sintéticos (ruído/silêncio) e variações de voz
(grave/aguda) aplicadas aos DOIS lados — assim o modelo aprende a palavra,
não o tom nem o volume.
"""
import subprocess, random
from pathlib import Path
import numpy as np, soundfile as sf, librosa
from common import SR, CLIP_LEN

AUDIO_DIR = Path("../audios")                 # ajuste p/ a pasta do Drive
DS = Path("dataset"); rng = np.random.default_rng(7); random.seed(7)

def to_wav(src, dst):
    subprocess.run(["ffmpeg","-v","error","-y","-i",str(src),
                    "-ar",str(SR),"-ac","1","-sample_fmt","s16",str(dst)], check=True)

def converter(sub_in, sub_out):
    out = DS / sub_out; out.mkdir(parents=True, exist_ok=True)
    fs = [f for e in ("*.m4a","*.mp4","*.ogg","*.wav") for f in (AUDIO_DIR/sub_in).glob(e)]
    for i, f in enumerate(fs):
        to_wav(f, out / f"{sub_out.replace('/','_')}_{i:03d}.wav")
    return len(fs)

def ruido_sintetico(n=250):
    out = DS / "negatives/ruido"; out.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        y = rng.standard_normal(CLIP_LEN).astype(np.float32)
        y *= rng.uniform(0.001, 0.6)          # de silêncio a ruído forte
        sf.write(out / f"ruido_{i:04d}.wav", y, SR)

def shift_voz(y, r):                            # desloca pitch+formantes juntos
    sp = librosa.resample(y, orig_sr=SR, target_sr=int(SR/r))
    return librosa.effects.time_stretch(sp, rate=1.0/r).astype(np.float32)

def variacoes_de_voz():
    """3 versões (grave/aguda/arrastada) de positivos E negativos — simetria."""
    for lado in ("positives", "negatives/fala"):
        src = DS / lado; dst = DS / (lado.split("/")[0] + "_variacoes")
        dst.mkdir(parents=True, exist_ok=True)
        for f in sorted(src.glob("*.wav")):
            y = librosa.load(f, sr=SR, mono=True)[0]
            for tag, fn in [("grave", lambda y: shift_voz(y, 0.88)),
                            ("aguda", lambda y: shift_voz(y, 1.12)),
                            ("arrast", lambda y: librosa.effects.time_stretch(y, rate=0.85))]:
                try: sf.write(dst / f"{f.stem}__{tag}.wav", fn(y).astype(np.float32), SR)
                except Exception: pass

if __name__ == "__main__":
    p = converter("socorro", "positives")
    n = converter("nao_socorro", "negatives/fala")
    ruido_sintetico()
    variacoes_de_voz()
    print(f"positivos: {p} | negativos (fala): {n} | + ruído sintético + variações de voz")
