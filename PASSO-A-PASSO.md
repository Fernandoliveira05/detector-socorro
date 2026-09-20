# Passo a passo + checagem de cobertura

## ✅ Cobrimos tudo que a ponderada pede?

### Requisitos
| Requisito | Coberto? | Onde |
|-----------|:---:|------|
| Capturar áudio via ESP32 + INMP441 | ✅ | `esp32/socorro_detector.ino` → `CaptureTask` (I2S) |
| Detectar anomalia com modelo pré-treinado | ✅ | `DetectTask` + `model_data.h` (TFLite Micro) |
| Arquitetura RTOS com **≥ 3 tarefas** sincronizadas | ✅ | **4 tarefas** (captura/features/detecção/alerta) |
| Medir e documentar latência de cada etapa | ✅ | logs `micros()` no firmware + `docs/relatorio_tecnico.md` |
| Alertar anomalia via LED/buzzer | ✅ | `AlertTask` → LED vermelho (GPIO23) + buzzer (GPIO27) |
| Resolver conflitos de concorrência | ✅ | mutex (`ringMutex`) + semáforo (`blockSem`) + fila (`featQueue`) |

### Entregáveis
| Entregável | Coberto? | Onde |
|-----------|:---:|------|
| Repositório com código-fonte | ✅ | `esp32/` + `modelo/` |
| Diagrama de tarefas RTOS (SVG) | ✅ | `docs/diagrama_rtos.svg` |
| Modelo de detecção (`.onnx`) | ✅ | `modelo/models/socorro.onnx` |
| Relatório técnico | ✅ | `docs/relatorio_tecnico.md` |
| Código de teste (simula e mede) | ✅ | `modelo/src/test_performance.py` |

### Extra (além do pedido)
- ✅ Simulação de **ligação real pra polícia** (Twilio) — `esp32/notificacao.ino`.
- ✅ Detecção **ao vivo no PC** pra demonstrar sem depender do chip — `modelo/src/demo_mic.py`.
- ✅ **RTOS explicado** didaticamente — `docs/RTOS-explicado.md`.

**Conclusão: tudo coberto.** Falta só a parte prática de montar e gravar no ESP32 (abaixo).

---

## 🔧 Passo a passo para implementar no ESP32

### Passo 1 — Materiais
- ESP32 DevKit + cabo USB
- Microfone INMP441
- LED vermelho + resistor 220–330 Ω
- Buzzer passivo (opcional)
- Protoboard + jumpers

### Passo 2 — Montar na protoboard
Siga **`esp32/LIGACAO_PROTOBOARD.md`**:
- INMP441: VDD→3V3, GND→GND, L/R→GND, WS→GPIO25, SCK→GPIO26, SD→GPIO33
- LED vermelho: GPIO23 → 220Ω → LED(+) → LED(−) → GND
- Buzzer: GPIO27 → buzzer → GND

### Passo 3 — Preparar o Arduino IDE
1. Adicione o suporte a ESP32 (Boards Manager → `esp32`).
2. Instale a biblioteca **TensorFlow Lite Micro** (ex.: `Chirale_TensorFlowLite`).
3. Placa: **ESP32 Dev Module**. Selecione a porta.

### Passo 4 — Credenciais (para a ligação Twilio — Fase 2)
1. Crie conta no Twilio, pegue SID/Token/número, verifique seu celular, crie o
   TwiML Bin. Detalhes em **`esp32/TWILIO_SETUP.md`**.
2. Copie `esp32/secrets_exemplo.h` → `esp32/secrets.h` e preencha.
   - Só quer a Fase 1 (LED)? Preencha `secrets.h` com valores fictícios — o WiFi
     falha e o LED/buzzer/serial funcionam offline.

### Passo 5 — Enviar o firmware
1. Abra a pasta `esp32/` no Arduino IDE (abra `socorro_detector.ino`).
2. **Upload**. Abra o **Monitor Serial** a **115200**.
3. Deve aparecer `Conectando WiFi ok` e `Detector de socorro iniciado.`

### Passo 6 — Testar (Fase 1: LED)
- Grite **"SOCORRO"** perto do microfone.
- ✅ Esperado: LED vermelho pisca ~8 s, buzzer bipa, Serial fica postando o alerta.

### Passo 7 — Testar (Fase 2: ligação)
- Grite "SOCORRO" com o WiFi conectado.
- ✅ Esperado: Serial mostra `[Twilio] ... HTTP 201` e **seu celular toca** com a
  mensagem de emergência.

### Passo 8 (opcional) — Melhorar com dados reais
- Grave mais socorros/negativos (`modelo/src/record_calibration.py`), retreine com
  `python modelo/pipeline.py treinar`. O `model_data.h`/`feat_norm.h` do `esp32/`
  são atualizados automaticamente.

---

## 🎤 Roteiro rápido de demonstração (checkpoint)
1. Mostre a **protoboard** e explique as 3 conexões (mic, LED, buzzer).
2. Abra `docs/RTOS-explicado.md` e explique as **4 tarefas + mutex/semáforo/fila**.
3. Rode ao vivo: grite socorro → LED pisca → celular toca. 🚨📞
4. Mostre o **modelo** (`.onnx`), o **relatório** e o **diagrama RTOS**.
5. Cite as **limitações honestas** (voz feminina/agudos) e como mediria melhorias
   (k-fold) — pega bem na banca.

> Dica: se o hardware falhar na hora, o `modelo/src/demo_mic.py` demonstra a
> detecção no PC (mesma lógica do firmware).
