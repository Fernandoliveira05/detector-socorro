# Detector de "SOCORRO" — Ponderada (Detector de Anomalias Acústicas)

Sistema que detecta a palavra **"socorro"** em tempo real num **ESP32 + microfone
INMP441**, acende um **LED vermelho** e **liga para a "polícia"** (simulação via
Twilio). Usa **FreeRTOS** (tarefas concorrentes) e um modelo de *keyword spotting*
(MFCC + rede neural) rodando com TensorFlow Lite Micro.

## 📁 O que tem em cada pasta

| Pasta | Conteúdo |
|-------|----------|
| **`esp32/`** | Tudo que vai pro chip (firmware C++) + como montar a protoboard. **Comece por `esp32/LEIA-ME.md`.** |
| **`modelo/`** | Treino do modelo em Python (dados, scripts, modelo `.onnx`). Veja `modelo/README.md`. |
| **`audios/`** | Os áudios gravados: `amigos/`, `pc_positivos/`, `pc_negativos/`, `deteccoes/`. |
| **`docs/`** | Relatório técnico, diagrama RTOS, **RTOS explicado**, o PDF da ponderada. |
| `_work/`, `_models/` | Internos (ambiente Python, modelos do whisper). Não precisa mexer. |

## 🚀 Por onde começar
1. **Entender o projeto**: [`docs/RTOS-explicado.md`](docs/RTOS-explicado.md) e
   [`modelo/GUIA.md`](docs/GUIA.md).
2. **Montar e rodar no ESP32**: [`PASSO-A-PASSO.md`](PASSO-A-PASSO.md) (guia completo)
   e [`esp32/LEIA-ME.md`](esp32/LEIA-ME.md).
3. **Ver os entregáveis**: modelo em `modelo/models/socorro.onnx`, relatório em
   `docs/relatorio_tecnico.md`, diagrama em `docs/diagrama_rtos.svg`.

## ✅ Entregáveis da ponderada (onde estão)
| Entregável | Local |
|-----------|-------|
| Código-fonte | `esp32/` (firmware) + `modelo/` (treino) |
| Modelo `.onnx` | `modelo/models/socorro.onnx` |
| Diagrama de tarefas RTOS | `docs/diagrama_rtos.svg` |
| Relatório técnico | `docs/relatorio_tecnico.md` |
| Código de teste | `modelo/src/test_performance.py` |

Checagem completa de cobertura + passo a passo: **[`PASSO-A-PASSO.md`](PASSO-A-PASSO.md)**
(ou abra **`guia.html`** no navegador para a versão interativa).

## 📦 O que NÃO vem neste repositório (ver `.gitignore`)
Para manter o repo leve e proteger a privacidade das vozes, ficam de fora:
- `audios/` — as gravações de voz (dados);
- `modelo/dataset/` e `modelo/metadata/` — dataset e features (derivados, regeneráveis);
- `_work/`, `_models/` — ambiente Python e modelos do whisper;
- `esp32/socorro_detector/secrets.h` — credenciais (crie a sua a partir de `esp32/socorro_detector/secrets_exemplo.h`).

O **modelo treinado** (`modelo/models/socorro.onnx`, `.tflite`, `model_data.h`,
`feat_norm.npz`) **está incluído**, então o firmware compila sem precisar treinar.

## 🔁 Regenerar o dataset/modelo (opcional)
Com os áudios em `audios/` e o ambiente em `_work/venv`:
```bash
source _work/venv/bin/activate
python modelo/pipeline.py tudo      # dados -> treino -> exporta (e sincroniza esp32/)
```
