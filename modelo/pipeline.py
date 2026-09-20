#!/usr/bin/env python3
"""
================================================================================
 PIPELINE do Detector de "SOCORRO"  —  ponto de entrada único e explicado
================================================================================
Em vez de decorar vários scripts numerados, use este:

  python pipeline.py explicar   # só MOSTRA o mapa do processo (não roda nada)
  python pipeline.py treinar    # re-treina o modelo (monta dados -> treina -> exporta)
  python pipeline.py tudo       # refaz TUDO do zero (a partir dos áudios brutos)

Cada etapa abaixo tem uma explicação em português simples — é o roteiro pra
entender e explicar o projeto na ponderada.
================================================================================
"""
import sys, subprocess
from pathlib import Path

SRC = Path(__file__).resolve().parent / "src"
PY = sys.executable

# (script, título, explicação amigável)  — na ordem lógica do processo
PREPARAR = [
    ("01_prepare_positives.py", "Separar as gravações",
     "Converte os áudios (celular/WhatsApp) p/ WAV 16kHz mono e separa em POSITIVOS "
     "(socorro) e NEGATIVOS. Confia na sua intenção: tudo que você gravou como socorro é positivo."),
    ("09_ingest_pc.py", "Áudios gravados no PC",
     "Pega o que você gravou no próprio microfone (positivos + negativos parecidos) — "
     "isso aproxima o modelo do microfone real que você usa."),
    ("02_mine_long.py", "Minerar áudios longos",
     "Nos áudios de vários segundos, acha o trecho onde alguém diz 'socorro' e recorta "
     "janelas de 1s (e usa o resto como fala negativa)."),
    ("03_make_noise.py", "Ruído sintético",
     "Gera ruído e silêncio artificiais como NEGATIVOS, pra o modelo não disparar à toa."),
    ("08_hard_negatives.py", "Negativos difíceis (voz erguida)",
     "Cria 'gritos' de OUTRAS palavras. Ensina que voz alta sozinha NÃO é socorro — só a palavra é."),
    ("10_add_mic_noise.py", "Ruído REAL do microfone",
     "Fatia gravações do ruído do seu ambiente como negativos — cobre o barulho de fundo real."),
    ("12_add_conversation.py", "Conversa real",
     "Fatia gravações de você conversando (sem socorro) como negativos — evita disparo em conversa."),
    ("13_voice_variants.py", "Variações de voz (3 por áudio)",
     "Cria 3 versões de cada áudio (grave, aguda, arrastada) simulando pessoas/entonações "
     "diferentes. Aplicado a positivos E negativos (simetria): o modelo aprende a PALAVRA, "
     "não o tom. Usado só no treino, sem vazar p/ teste. Foi o que corrigiu 'agudo = socorro'."),
]
TREINAR = [
    ("04_build_dataset.py", "Montar o dataset (features)",
     "Padroniza tudo em 1s, aplica AUMENTOS (ruído, eco, etc.) e transforma o som em "
     "MFCC (a 'impressão digital' do áudio, 49x16 números). Separa treino/validação/teste."),
    ("05_train.py", "Treinar a rede",
     "Treina uma CNN pequena pra dizer 'socorro' vs 'não'. Escolhe o melhor limiar e mede acurácia."),
    ("06_export.py", "Exportar o modelo",
     "Salva socorro.onnx (entregável), .tflite e o C array pro ESP32."),
]

def rodar(passos):
    for i, (script, titulo, _) in enumerate(passos, 1):
        print(f"\n{'='*70}\n▶ ETAPA {i}/{len(passos)}: {titulo}   ({script})\n{'='*70}")
        r = subprocess.run([PY, str(SRC / script)])
        if r.returncode != 0:
            print(f"⚠ etapa {script} retornou erro {r.returncode} — seguindo mesmo assim.")

def explicar():
    print(__doc__)
    print("MAPA DO PROCESSO\n" + "-"*70)
    print("\n【 FASE 1 — PREPARAR OS DADOS 】  (junta positivos e negativos variados)")
    for s, t, e in PREPARAR:
        print(f"\n  • {t}  ({s})\n    {e}")
    print("\n【 FASE 2 — TREINAR E EXPORTAR 】")
    for s, t, e in TREINAR:
        print(f"\n  • {t}  ({s})\n    {e}")
    print("\n" + "-"*70)
    print("DEPOIS: teste ao vivo com  ->  python src/demo_mic.py")
    print("        performance/latência ->  python src/test_performance.py")

def main():
    modo = sys.argv[1] if len(sys.argv) > 1 else "explicar"
    if modo == "explicar":
        explicar()
    elif modo == "treinar":
        rodar(TREINAR)
        print("\n✓ Modelo re-treinado e exportado em models/")
    elif modo == "tudo":
        rodar(PREPARAR + TREINAR)
        print("\n✓ Pipeline completo executado.")
    else:
        print("Modo inválido. Use: explicar | treinar | tudo")

if __name__ == "__main__":
    main()
