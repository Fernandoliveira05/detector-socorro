# modelo/ — Treino do detector de "SOCORRO" (Python)

Aqui fica o treino do modelo de *keyword spotting* (MFCC + CNN pequena) que roda no
ESP32. O firmware está em [`../esp32/`](../esp32/); os docs em [`../docs/`](../docs/).

> 👉 **Para entender/apresentar:** [`../docs/GUIA.md`](../docs/GUIA.md) (linguagem
> simples) e `python pipeline.py explicar` (mostra o mapa do processo). Você não
> precisa mexer nos scripts numerados diretamente.

## Estrutura
```
modelo/
  pipeline.py     ponto de entrada (explicar | treinar | tudo)
  src/            scripts do pipeline (dados, treino, export, demo, testes)
  dataset/        positivos e negativos (WAV 16k mono)
  models/         socorro.onnx (entregável) + .tflite + C array + feat_norm + metrics.json
  metadata/       dataset.npz e manifests
```
Os áudios brutos ficam em [`../audios/`](../audios/) (amigos, pc_positivos, pc_negativos, deteccoes).

## Ambiente
```bash
source ../_work/venv/bin/activate      # TF 2.15, librosa, onnx, tf2onnx, onnxruntime
```

## Uso rápido (recomendado)
```bash
python pipeline.py explicar   # mostra o processo passo a passo (não roda nada)
python pipeline.py treinar    # reconstrói dataset + treina + exporta
python pipeline.py tudo       # refaz do zero (a partir dos áudios brutos)
```
O `treinar`/`tudo` já exporta `socorro.onnx`, `.tflite`, o C array e **sincroniza o
`../esp32/`** (model_data.h + feat_norm.h).

## Demo ao vivo (PC — espelha o firmware)
```bash
python src/demo_mic.py            # threshold da config congelada (0.55) + debounce
python src/demo_mic.py 0.45       # threshold manual
```
Cada detecção é salva em `../audios/deteccoes/` para revisão (*active learning*):
aprove e reincorpore com `python src/11_ingest_detections.py`.

## Testes
```bash
python src/test_performance.py         # acurácia + latência
python src/diag_kfold.py               # validação cruzada (teto + variância)
python src/test_negative_phrases.py    # frases negativas (TTS) + verificação whisper
```

## Config congelada
Threshold **0.55**, debounce **6 janelas** (~375 ms), passo **62 ms**, gate RMS **0.005**
(ver `models/metrics.json` → `frozen`). Features com **normalização global** +
**label smoothing** (probabilidades estáveis). Limitações conhecidas (voz feminina/
agudos) documentadas em [`../docs/relatorio_tecnico.md`](../docs/relatorio_tecnico.md).
