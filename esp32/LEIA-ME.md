# ESP32 — Detector de "Socorro" (o que vai no chip)

Esta pasta tem **tudo que roda no ESP32**. Abra a pasta inteira no Arduino IDE
(o sketch é `socorro_detector.ino`; os outros arquivos entram junto).

## O que cada arquivo é
| Arquivo | Para que serve |
|---------|----------------|
| `socorro_detector.ino` | Programa principal: as **4 tarefas RTOS** (captura, features, detecção, alerta) |
| `notificacao.ino` | WiFi + ligação/SMS via Twilio (separado p/ o principal ficar simples) |
| `features.h` / `features.cpp` | Calcula RMS e MFCC do áudio (as "features") |
| `feat_norm.h` | Números de normalização do MFCC (gerados no treino) |
| `model_data.h` | O modelo treinado (rede neural) em formato C |
| `config.h` | Pinos e parâmetros (mexa aqui se trocar de pino) |
| `secrets_exemplo.h` | Modelo de credenciais → copie p/ `secrets.h` e preencha |

## Passo a passo (resumo)

### 1. Montar na protoboard
Siga **[LIGACAO_PROTOBOARD.md](LIGACAO_PROTOBOARD.md)**. Em resumo:
- **INMP441** (microfone): VDD→3V3, GND→GND, L/R→GND, WS→GPIO25, SCK→GPIO26, SD→GPIO33
- **LED vermelho**: GPIO23 → resistor 220Ω → LED → GND
- **Buzzer** (opcional): GPIO27 → buzzer → GND

### 2. Preparar o Arduino IDE
1. Instale o suporte a ESP32: *Preferences → Additional Boards* →
   `https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json`
   depois *Boards Manager → esp32*.
2. Instale a biblioteca **TensorFlow Lite Micro** (ex.: `Chirale_TensorFlowLite`
   no Library Manager, ou `tflite-micro-arduino-examples`).
3. Selecione a placa **ESP32 Dev Module** e a porta COM.

### 3. Configurar credenciais (para a ligação — Fase 2)
```
copie  secrets_exemplo.h  →  secrets.h   e preencha WiFi + Twilio
```
Como pegar as credenciais Twilio: **[TWILIO_SETUP.md](TWILIO_SETUP.md)**.
(Se quiser só a Fase 1 — LED vermelho, sem ligação — crie um `secrets.h` com
valores fictícios; o WiFi falha e o resto funciona offline.)

### 4. Enviar e testar
1. Clique em **Upload**. Abra o **Monitor Serial** (115200).
2. Grite **"SOCORRO"** perto do microfone.
3. Esperado:
   - LED vermelho **pisca ~8 s** + buzzer;
   - Serial mostra `SOCORRO! p=...` e fica **postando** o alerta;
   - (Fase 2) seu **celular toca** com a mensagem de emergência.

## Como funciona por dentro
- Entenda a arquitetura RTOS em **[../docs/RTOS-explicado.md](../docs/RTOS-explicado.md)**.
- O modelo foi treinado na pasta **[../modelo/](../modelo/)**.

> Se retreinar o modelo (`../modelo/`), o `model_data.h` e o `feat_norm.h` desta
> pasta são atualizados automaticamente pelo passo de exportação.
