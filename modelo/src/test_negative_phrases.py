#!/usr/bin/env python3
"""
Testa o modelo em FRASES contínuas negativas (cenário real do ESP32).
- Gera frases PT-BR com o TTS do macOS (say), incluindo palavras traiçoeiras
  ("corro", "morro", "horror", "controle", "concorro").
- Também varre áudios longos reais.
- Janela deslizante 1s (hop 0.25s) + gate de RMS.
- Whisper como VERIFICADOR: em cada janela disparada, transcreve o que era.
"""
import sys, subprocess, tempfile
from pathlib import Path
import numpy as np, onnxruntime as ort, librosa, soundfile as sf
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import SR, CLIP_LEN, mfcc

PROJ = Path(__file__).resolve().parents[1]
ROOT = PROJ.parent
MODEL_WH = ROOT / "_models" / "ggml-small.bin"
sess = ort.InferenceSession(str(PROJ/"models"/"socorro.onnx"), providers=["CPUExecutionProvider"])
IN = sess.get_inputs()[0].name
THR = 0.8
GATE = 0.02
HOP = CLIP_LEN // 4

FRASES = [
    ("neg", "Bom dia, tudo bem com você hoje?"),
    ("neg", "Eu corro no parque toda manhã bem cedo."),
    ("neg", "Que horror, esse filme é muito assustador."),
    ("neg", "Vou subir o morro para ver a paisagem."),
    ("neg", "O controle da televisão sumiu de novo."),
    ("neg", "Preciso comprar pão, leite e café hoje."),
    ("neg", "Nós concorremos ao mesmo cargo na empresa."),
    ("neg", "Cadê o carregador do meu computador?"),
    ("neg", "A prova de cálculo foi bastante difícil."),
    ("pos", "Socorro! Socorro!"),   # controle positivo (deve disparar)
]
VOZES = ["Luciana", "Rocko", "Eddy"]

def tts(voz, texto, dst):
    aiff = dst.with_suffix(".aiff")
    subprocess.run(["say", "-v", voz, "-o", str(aiff), texto], check=True)
    subprocess.run(["ffmpeg","-v","error","-y","-i",str(aiff),"-ar",str(SR),
                    "-ac","1", str(dst)], check=True)
    aiff.unlink(missing_ok=True)

def whisper_seg(seg):
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as t:
        sf.write(t.name, seg, SR)
        of = t.name[:-4]
        subprocess.run(["whisper-cli","-m",str(MODEL_WH),"-l","pt","-nt","-np",
                        "-otxt","-of",of,t.name],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        txt = Path(of+".txt")
        r = txt.read_text(encoding="utf-8").strip() if txt.exists() else ""
    Path(t.name).unlink(missing_ok=True)
    return r.replace("\n"," ")

def scan(y):
    if len(y) < CLIP_LEN: y = np.pad(y, (0, CLIP_LEN-len(y)))
    hits, pmax = [], 0.0
    for a in range(0, len(y)-CLIP_LEN+1, HOP):
        seg = y[a:a+CLIP_LEN]
        if np.sqrt(np.mean(seg**2)) < GATE: continue
        p = float(sess.run(None, {IN: mfcc(seg)[None,...,None].astype(np.float32)})[0][0,1])
        pmax = max(pmax, p)
        if p >= THR: hits.append((a/SR, p, seg))
    return pmax, hits

def main():
    tmp = PROJ / "_tts"; tmp.mkdir(exist_ok=True)
    print(f"threshold={THR}  gate={GATE}\n")
    fp_total = fp_files = 0
    print("=== FRASES TTS (PT-BR, 3 vozes) ===")
    for kind, txt in FRASES:
        worst = 0.0; allhits = []
        for voz in VOZES:
            dst = tmp / f"{voz}_{abs(hash(txt))%9999}.wav"
            tts(voz, txt, dst)
            pmax, hits = scan(librosa.load(dst, sr=SR, mono=True)[0])
            worst = max(worst, pmax); allhits += hits
        mark = "🚨 disparou" if worst >= THR else "— ok"
        tag = "(POS control)" if kind=="pos" else ""
        print(f"  [{mark:12s}] pmax={worst:.2f}  “{txt}” {tag}")
        for t,p,seg in allhits[:2]:
            print(f"        janela {t:.1f}s p={p:.2f} -> whisper ouviu: {whisper_seg(seg)!r}")
        if kind=="neg" and worst>=THR:
            fp_files += 1; fp_total += len(allhits)

    print("\n=== ÁUDIOS LONGOS REAIS (frases contínuas) ===")
    for f in sorted((PROJ/"dataset"/"long_mined"/"src").glob("*.wav")):
        pmax, hits = scan(librosa.load(f, sr=SR, mono=True)[0])
        mark = "🚨" if pmax>=THR else "—"
        print(f"  [{mark}] pmax={pmax:.2f}  {f.name}")
        for t,p,seg in hits[:2]:
            print(f"        janela {t:.1f}s p={p:.2f} -> whisper: {whisper_seg(seg)!r}")

    print(f"\nRESUMO frases TTS negativas: {fp_files} frase(s) com falso positivo.")

if __name__ == "__main__":
    main()
