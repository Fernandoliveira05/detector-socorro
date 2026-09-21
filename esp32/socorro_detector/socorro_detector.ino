// ============================================================================
//  Detector de "SOCORRO" — ESP32 + INMP441 + FreeRTOS + TensorFlow Lite Micro
//  Ponderada: Detector de Anomalias Acústicas
//
//  Arquitetura RTOS (3 tarefas sincronizadas):
//    [T1] CaptureTask  (prio ALTA)  : lê I2S -> preenche buffer circular
//    [T2] FeatureTask  (prio MÉDIA) : janela de 1s -> RMS + MFCC -> fila
//    [T3] DetectTask   (prio BAIXA) : modelo TFLM -> threshold+debounce -> alerta
//
//  Sincronização:
//    - ringMutex  (mutex)     : protege o buffer circular (T1 escreve, T2 lê)
//    - blockSem   (semáforo)  : T1 sinaliza "novo bloco de áudio" p/ T2
//    - featQueue  (fila)      : T2 envia features p/ T3
//
//  Features idênticas ao treino (ver config.h / common.py).
// ============================================================================
#include <driver/i2s.h>
#include "soc/soc.h"           // p/ desligar o detector de brownout
#include "soc/rtc_cntl_reg.h"
#include "config.h"
#include "features.h"
#include "model_data.h"

// --- TensorFlow Lite Micro ---
#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/micro/micro_mutable_op_resolver.h"
#include "tensorflow/lite/micro/system_setup.h"
#include "tensorflow/lite/schema/schema_generated.h"

// ---------------- Buffer circular (compartilhado T1<->T2) ----------------
static int16_t ring[RING_LEN];                  // áudio como int16 (economia de RAM)
static volatile uint32_t writeIdx = 0;          // próxima posição de escrita
static SemaphoreHandle_t ringMutex;
static SemaphoreHandle_t blockSem;              // T1 -> T2 (novo bloco pronto)

// ---------------- Fila de features (T2 -> T3) ----------------
typedef struct { float mfcc[N_FRAMES * N_MFCC]; uint32_t t_capture_us; } Feature;
static QueueHandle_t featQueue;

// ---------------- Estado de alerta (T3 -> T4) ----------------
static volatile uint32_t alertUntil = 0;      // millis até quando o alerta fica ativo
static volatile float    lastProb = 0.0f;

// ---------------- TFLite Micro ----------------
constexpr int kArenaSize = 28 * 1024;   // o modelo pede ~25 KB; 28 KB dá margem
static uint8_t tensor_arena[kArenaSize];
static tflite::MicroInterpreter* interpreter = nullptr;
static TfLiteTensor* input = nullptr;
static TfLiteTensor* output = nullptr;

// ============================================================================
// T1 — Captura de áudio (alta prioridade): I2S -> buffer circular
// ============================================================================
void CaptureTask(void* arg) {
  const int CHUNK = 256;                         // lê o I2S em blocos pequenos (economia de RAM)
  static int32_t raw[256];
  size_t nbytes; int acc = 0;
  while (true) {
    i2s_read(I2S_PORT, raw, CHUNK * sizeof(int32_t), &nbytes, portMAX_DELAY);
    int got = nbytes / sizeof(int32_t);
    xSemaphoreTake(ringMutex, portMAX_DELAY);
    for (int i = 0; i < got; i++) {
      // INMP441: amostra de 24 bits alinhada ao topo de 32 bits -> pega os 16 bits altos
      ring[writeIdx] = (int16_t)(raw[i] >> 16);
      writeIdx = (writeIdx + 1) % RING_LEN;
    }
    xSemaphoreGive(ringMutex);
    acc += got;                                  // avisa T2 a cada STEP_SAMPLES (~62 ms)
    if (acc >= STEP_SAMPLES) { acc = 0; xSemaphoreGive(blockSem); }
  }
}

// ============================================================================
// T2 — Extração de features (prioridade média): RMS + MFCC -> fila
// ============================================================================
void FeatureTask(void* arg) {
  Feature feat;
  while (true) {
    xSemaphoreTake(blockSem, portMAX_DELAY);     // espera bloco novo de T1
    uint32_t t0 = micros();

    // pega o índice atual do buffer (seção crítica curta protegida por mutex)
    xSemaphoreTake(ringMutex, portMAX_DELAY);
    int end = (int)writeIdx;
    xSemaphoreGive(ringMutex);
    // lê a janela de 1 s DIRETO do ring (a captura escreve à frente; só alcançaria
    // esta janela depois de ~1 s, e o MFCC leva ~30 ms -> seguro sem cópia)

    // gate de energia (feature RMS do enunciado): pula fundo/silêncio
    if (compute_rms(ring, end) < RMS_GATE) continue;

    compute_mfcc(ring, end, feat.mfcc);
    feat.t_capture_us = t0;
    xQueueSend(featQueue, &feat, 0);             // envia p/ T3 (descarta se cheia)

    uint32_t dt = micros() - t0;
    static uint32_t maxFeat = 0;
    if (dt > maxFeat) { maxFeat = dt; Serial.printf("[T2] MFCC latencia max: %u us\n", dt); }
  }
}

// ============================================================================
// T3 — Detecção de anomalia (baixa prioridade): modelo -> alerta
// ============================================================================
void DetectTask(void* arg) {
  Feature feat;
  int consec = 0;
  uint32_t lastAlert = 0;
  while (true) {
    if (xQueueReceive(featQueue, &feat, portMAX_DELAY) != pdTRUE) continue;
    uint32_t t0 = micros();

    // quantiza entrada (int8) usando escala/zero-point do tensor
    for (int i = 0; i < N_FRAMES * N_MFCC; i++) {
      int v = (int)roundf(feat.mfcc[i] / input->params.scale) + input->params.zero_point;
      v = v < -128 ? -128 : (v > 127 ? 127 : v);
      input->data.int8[i] = (int8_t)v;
    }
    if (interpreter->Invoke() != kTfLiteOk) { Serial.println("Invoke falhou"); continue; }

    // dequantiza saída [nao, socorro]
    float p = (output->data.int8[1] - output->params.zero_point) * output->params.scale;

    uint32_t now = millis();
    consec = (p >= THRESHOLD) ? consec + 1 : 0;
    if (consec >= CONSEC && (now - lastAlert) > 1500) {
      lastAlert = now; consec = 0;
      lastProb = p;
      alertUntil = now + ALERT_HOLD_MS;                // ATIVA o alerta (T4 cuida do resto)
      uint32_t e2e = micros() - feat.t_capture_us;     // latência captura->alerta
      Serial.printf("[T3] SOCORRO! p=%.2f  latencia ponta-a-ponta=%u us\n", p, e2e);
    }
    uint32_t dt = micros() - t0;
    static uint32_t maxInf = 0;
    if (dt > maxInf) { maxInf = dt; Serial.printf("[T3] inferencia latencia max: %u us\n", dt); }
  }
}

// ============================================================================
// T4 — Alerta/Notificação: enquanto o alerta está ativo, pisca o LED VERMELHO
// e fica "postando" o aviso periodicamente (serial agora; HTTP na Fase 2).
// ============================================================================
void postarAlerta(float p);      // Fase 1: serial (posta repetido) — abaixo
void ligarParaPolicia(float p);  // Fase 2: Twilio — em notificacao.ino
void wifiSetup();                //           WiFi              — em notificacao.ino

void AlertTask(void* arg) {
  bool ledOn = false, wasActive = false;
  uint32_t tBlink = 0, tPost = 0, lastCall = 0;
  while (true) {
    uint32_t now = millis();
    bool active = (int32_t)(alertUntil - now) > 0;
    if (active) {
      // borda de subida -> LIGA pra polícia UMA vez (cooldown de 30 s)
      if (!wasActive && (now - lastCall > 30000 || lastCall == 0)) {
        lastCall = now; ligarParaPolicia(lastProb);
      }
      if (now - tBlink >= BLINK_MS) {                  // pisca o LED vermelho
        ledOn = !ledOn; digitalWrite(PIN_LED_RED, ledOn); tBlink = now;
        if (ledOn) tone(PIN_BUZZER, 2000, 120);
      }
      if (now - tPost >= POST_INTERVAL_MS) {           // "posta" o alerta (repetido)
        tPost = now; postarAlerta(lastProb);
      }
    } else if (ledOn) {
      ledOn = false; digitalWrite(PIN_LED_RED, LOW);
    }
    wasActive = active;
    vTaskDelay(pdMS_TO_TICKS(20));
  }
}

void postarAlerta(float p) {
  Serial.printf("[ALERTA] SOCORRO detectado (p=%.2f) — LED vermelho ligado, postando...\n", p);
}
// wifiSetup() e ligarParaPolicia() estão em notificacao.ino (WiFi + Twilio).

// ============================================================================
// Setup
// ============================================================================
void setupI2S() {
  i2s_config_t cfg = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = SR,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 8,
    .dma_buf_len = 256,
    .use_apll = false,
    .tx_desc_auto_clear = false,
    .fixed_mclk = 0
  };
  i2s_pin_config_t pins = {
    .bck_io_num = I2S_SCK, .ws_io_num = I2S_WS,
    .data_out_num = I2S_PIN_NO_CHANGE, .data_in_num = I2S_SD
  };
  i2s_driver_install(I2S_PORT, &cfg, 0, NULL);
  i2s_set_pin(I2S_PORT, &pins);
}

void setupModel() {
  const tflite::Model* model = tflite::GetModel(g_socorro_model);
  static tflite::MicroMutableOpResolver<16> resolver;
  resolver.AddConv2D();
  resolver.AddDepthwiseConv2D();
  resolver.AddMaxPool2D();
  resolver.AddAveragePool2D();
  resolver.AddFullyConnected();
  resolver.AddReshape();
  resolver.AddSoftmax();
  resolver.AddMean();              // GlobalAveragePooling2D
  resolver.AddMul();               // BatchNormalization (escala) -> MUL
  resolver.AddAdd();               // BatchNormalization (offset) -> ADD
  resolver.AddQuantize();
  resolver.AddDequantize();
  static tflite::MicroInterpreter s(model, resolver, tensor_arena, kArenaSize);
  interpreter = &s;
  interpreter->AllocateTensors();
  input  = interpreter->input(0);
  output = interpreter->output(0);
}

void setup() {
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);   // desliga o detector de brownout (contorno p/ fonte no limite)
  Serial.begin(115200);
  pinMode(PIN_LED, OUTPUT); pinMode(PIN_BUZZER, OUTPUT);
  pinMode(PIN_LED_RED, OUTPUT); digitalWrite(PIN_LED_RED, LOW);
  features_init();
  wifiSetup();          // conecta WiFi p/ a ligação Twilio (Fase 2)
  setupI2S();
  setupModel();

  ringMutex = xSemaphoreCreateMutex();
  blockSem  = xSemaphoreCreateBinary();
  featQueue = xQueueCreate(4, sizeof(Feature));

  // prioridades: captura > features > detecção (como pede o enunciado)
  xTaskCreatePinnedToCore(CaptureTask, "capture", 4096, NULL, 5, NULL, 0);
  xTaskCreatePinnedToCore(FeatureTask, "feature", 8192, NULL, 3, NULL, 1);
  xTaskCreatePinnedToCore(DetectTask,  "detect",  8192, NULL, 2, NULL, 1);
  xTaskCreatePinnedToCore(AlertTask,   "alert",   4096, NULL, 1, NULL, 1);
  Serial.println("Detector de socorro iniciado.");
}

void loop() { vTaskDelay(portMAX_DELAY); }   // tudo roda nas tasks
