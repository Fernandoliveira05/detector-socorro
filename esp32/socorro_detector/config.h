// ============================================================================
// config.h — parâmetros do detector de "socorro" (ESP32 + INMP441 + FreeRTOS)
// Devem casar com projeto/src/common.py (mesma extração de features do treino).
// ============================================================================
#pragma once

// ---- Áudio / features (idênticos ao treino em common.py) ----
#define SR            16000          // taxa de amostragem (Hz)
#define CLIP_LEN      16000          // 1.0 s -> amostras por janela de decisão
#define WIN_LEN       480            // 30 ms  (janela do frame de MFCC)
#define HOP_LEN       320            // 20 ms  (passo entre frames)
#define N_FFT         512
#define N_MELS        40
#define N_MFCC        16
#define N_FRAMES      49             // 1 + (CLIP_LEN-WIN_LEN)/HOP_LEN
#define FMIN          20.0f
#define FMAX          8000.0f        // SR/2

// ---- Decisão (config "congelada", ver metrics.json) ----
#define THRESHOLD     0.80f          // limiar validado no INMP441: 9/9 socorro, 0/5 falso-positivo
#define CONSEC        3              // ~375 ms sustentados (3 janelas de ~125 ms)
#define RMS_GATE      0.005f         // abaixo disso = fundo/silêncio (não classifica)
#define STEP_SAMPLES  2000           // ~125 ms: passo da janela (MFCC leva ~67ms, dá folga de CPU)

// ---- Buffer circular ----
// int16 + folga mínima segura (a leitura da janela leva ~30ms; 512 amostras = 32ms)
#define RING_LEN      (CLIP_LEN + 512)

// ---- Pinos ----
// INMP441 (I2S):
#define I2S_SCK       26             // BCLK
#define I2S_WS        25             // LRCL / WS
#define I2S_SD        33             // DOUT do microfone -> DIN do ESP32
#define I2S_PORT      I2S_NUM_0
// Alerta:
#define PIN_LED       2              // LED onboard (status)
#define PIN_LED_RED   23             // LED VERMELHO externo (alerta de socorro)
#define PIN_BUZZER    27             // buzzer (opcional)

// ---- Ganho de entrada do INMP441 ----
// Pega os bits altos do sample de 24 bits. Quanto MAIOR o shift, MENOS volume
// (mais headroom, menos estouro). 16 = padrão; suba (18, 19, 20) se estourar.
#define GAIN_SHIFT    18

// ---- Modo de gravação (domain adaptation) ----
// 1 = transmite o áudio cru do INMP441 pela serial (921600 baud) p/ gravar e retreinar.
// 0 = funcionamento normal (detector).
#define DUMP_AUDIO    0

// ---- Ligação Twilio ----
// 0 = notificação via GATEWAY (o notebook escuta a serial e faz a ligação). Recomendado:
//     o HTTPS no próprio ESP32 esbarra em memória/watchdog junto com o modelo + WiFi.
// 1 = tenta ligar direto do ESP (pode reiniciar no handshake TLS).
#define USE_ONDEVICE_CALL  0

// ---- Comportamento do alerta ----
#define ALERT_HOLD_MS   8000         // mantém o alerta ativo por 8 s após detectar
#define BLINK_MS        250          // período do piscar do LED vermelho
#define POST_INTERVAL_MS 1500        // a cada 1.5 s "posta" o alerta (serial/HTTP)
