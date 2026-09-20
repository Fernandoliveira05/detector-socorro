#!/usr/bin/env python3
"""
Etapa 11 (active learning): incorpora ao treino os disparos que VOCÊ aprovou.

Fluxo:
  1. Rode o demo -> disparos são salvos em "Socorros Detectados/".
  2. OUÇA a pasta e APAGUE os que não forem socorro (deixe só os corretos).
  3. Rode este script -> copia os aprovados p/ dataset/positives/ (prefixo det_).
  4. bash projeto/src/retrain.sh

Assim o modelo aprende com casos reais do uso, sem contaminar com falsos positivos.
"""
import shutil
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
SRC = PROJ.parent / "audios" / "deteccoes"
DST = PROJ / "dataset" / "positives"

def main():
    if not SRC.exists():
        print("Pasta 'Socorros Detectados' ainda não existe (rode o demo primeiro)."); return
    wavs = sorted(SRC.glob("*.wav"))
    if not wavs:
        print("Nenhum disparo na pasta."); return
    n = 0
    for f in wavs:
        dst = DST / f"det_{f.name}"
        if not dst.exists():
            shutil.copy(f, dst); n += 1
    print(f"{n} disparos aprovados copiados p/ dataset/positives/.")
    print("Agora rode: bash projeto/src/retrain.sh")
    print("(dica: mova os já incorporados p/ uma subpasta pra não reimportar)")

if __name__ == "__main__":
    main()
