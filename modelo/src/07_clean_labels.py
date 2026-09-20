#!/usr/bin/env python3
"""
Etapa 7: identifica positivos provavelmente MAL rotulados.
Usa o modelo (via SavedModel) p/ pontuar cada positivo e cruza com a
transcrição do whisper. Positivos com prob muito baixa E cuja transcrição
não tem pista fonética de socorro são candidatos a virar negativo.
"""
import sys, csv, re, unicodedata
from pathlib import Path
import numpy as np, tensorflow as tf, librosa
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import SR, fix_length, mfcc

PROJ = Path(__file__).resolve().parents[1]
ROOT = PROJ.parent
serve = tf.saved_model.load(str(PROJ/"models"/"socorro_savedmodel")).signatures["serve"]

def deacc(s):
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn").lower()
SOC = re.compile(r"soc|sacarr|corr|couro|curro|cool|saca")

# transcrições originais por slug
trans = {}
for r in csv.DictReader(open(ROOT/"_work"/"transcricoes.csv", encoding="utf-8"), delimiter="|"):
    slug = (r["arquivo"].replace(".m4a.mp4","").replace(".mp4","")
            .replace(".ogg","").replace(".mpeg","").replace(" ","_"))
    trans[slug] = r["transcricao"]

def prob(path):
    y = fix_length(librosa.load(path, sr=SR, mono=True)[0])
    x = mfcc(y)[None, ..., None].astype(np.float32)
    out = serve(mfcc=tf.constant(x))
    return float(list(out.values())[0].numpy()[0, 1])

rows = []
for f in sorted((PROJ/"dataset"/"positives").glob("*.wav")):
    p = prob(f)
    tx = trans.get(f.stem, "(minerado)")
    foneme = bool(SOC.search(deacc(tx))) or f.stem.startswith("mined_")
    rows.append((p, f.name, foneme, tx))

rows.sort()
print("=== 15 positivos com menor probabilidade (candidatos a rótulo errado) ===")
for p, name, foneme, tx in rows[:15]:
    flag = "" if foneme else "  <-- SEM pista de socorro"
    print(f"  p={p:.2f}  {name:42s} {tx[:40]!r}{flag}")
