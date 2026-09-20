#!/usr/bin/env python3
"""
Etapa 1: converte as gravações em WAV 16kHz mono e separa:
  - POSITIVOS  -> dataset/positives/        (gritos de "socorro")
  - NEGATIVOS  -> dataset/negatives/from_recordings/ (fala PT que não é socorro)
  - LONGOS     -> dataset/long_mined/src/    (áudios > LONG_S, minerados na etapa 2)

Decisão de rótulo (acordada com o usuário): confiamos na intenção da gravação —
todo clipe curto é "socorro", EXCETO a blocklist abaixo (transcrições claramente
de outra coisa), que vira negativo em português.
"""
import csv, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # raiz do workspace
PROJ = Path(__file__).resolve().parents[1]          # pasta "modelo"
AUDIO_DIR = ROOT / "audios" / "amigos"              # gravações dos amigos
CSV  = ROOT / "_work" / "transcricoes.csv"
SR   = 16000
LONG_S = 10.0                                        # > 10s => minerar por segmentos

POS_DIR = PROJ / "dataset" / "positives"
NEG_DIR = PROJ / "dataset" / "negatives" / "from_recordings"
LONG_DIR = PROJ / "dataset" / "long_mined" / "src"
for d in (POS_DIR, NEG_DIR, LONG_DIR):
    d.mkdir(parents=True, exist_ok=True)

# Arquivos cuja transcrição é claramente OUTRA coisa (não socorro) -> negativos PT.
# Blocklist ENXUTA: só frases claramente conversacionais (não-grito). Os clipes
# curtos tipo-grito que o whisper mastigava (28/36/46/80, IPT 46) foram RECLASSIFICADOS
# como positivos — são socorro, conforme intenção do usuário (whisper erra gritos).
BLOCKLIST = {
    "Engenharia Civil e Ambiental.m4a.mp4",            # Obrigado!
    "Engenharia Civil e Ambiental 7.m4a.mp4",          # O que é isso?
    "Rua MMDC 20.m4a.mp4",                             # É muito legal
    "Rua MMDC 73.m4a.mp4",                             # O que é isso?
    "WhatsApp Ptt 2026-09-16 at 01.12.06.ogg",         # Obrigado Lefe
    "INSTITUTO DE PESQUISAS TECNOLOGICAS CRECHE 28.m4a.mp4",  # É, eu estou tão... Tá bom
    "INSTITUTO DE PESQUISAS TECNOLOGICAS CRECHE 31.m4a.mp4",  # Come on
    "INSTITUTO DE PESQUISAS TECNOLOGICAS CRECHE 34.m4a.mp4",  # Deixa eu pensar...
    "INSTITUTO DE PESQUISAS TECNOLOGICAS CRECHE 65.m4a.mp4",  # Ah, é tão legal
    "INSTITUTO DE PESQUISAS TECNOLOGICAS CRECHE 71.m4a.mp4",  # Para, Renanzinho!
    "INSTITUTO DE PESQUISAS TECNOLOGICAS CRECHE 58.m4a.mp4",  # notícia (socorro embutido)
    "INSTITUTO DE PESQUISAS TECNOLOGICAS CRECHE 61.m4a.mp4",  # música (socorro embutido)
}

def to_wav(src: Path, dst: Path):
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(src),
         "-ar", str(SR), "-ac", "1", "-sample_fmt", "s16", str(dst)],
        check=True)

def slug(name: str) -> str:
    return (name.replace(".m4a.mp4", "").replace(".mp4", "").replace(".ogg", "")
            .replace(".mpeg", "").replace(" ", "_"))

def main():
    rows = list(csv.DictReader(open(CSV, encoding="utf-8"), delimiter="|"))
    n_pos = n_neg = n_long = 0
    manifest = []
    for r in rows:
        fn = r["arquivo"]
        dur = float(r["duracao_s"] or 0)
        src = AUDIO_DIR / fn
        if not src.exists():
            print("!! não encontrado:", fn); continue
        if dur > LONG_S:
            dst = LONG_DIR / (slug(fn) + ".wav")
            to_wav(src, dst); n_long += 1
            manifest.append((fn, "long", str(dst.relative_to(PROJ)), r["transcricao"]))
        elif fn in BLOCKLIST:
            dst = NEG_DIR / (slug(fn) + ".wav")
            to_wav(src, dst); n_neg += 1
            manifest.append((fn, "negative", str(dst.relative_to(PROJ)), r["transcricao"]))
        else:
            dst = POS_DIR / (slug(fn) + ".wav")
            to_wav(src, dst); n_pos += 1
            manifest.append((fn, "positive", str(dst.relative_to(PROJ)), r["transcricao"]))

    mpath = PROJ / "metadata" / "manifest_etapa1.csv"
    with open(mpath, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["arquivo_orig", "classe", "wav", "transcricao"])
        w.writerows(manifest)

    print(f"POSITIVOS: {n_pos}")
    print(f"NEGATIVOS (das gravações): {n_neg}")
    print(f"LONGOS p/ minerar: {n_long}")
    print("manifest:", mpath.relative_to(ROOT))

if __name__ == "__main__":
    main()
