# Detector de Anomalias Acústicas — Detecção da palavra "SOCORRO"

**Ponderada — Sistemas Embarcados / RTOS + Edge ML**

---

## 1. Objetivo e escolha do som

Sistema embarcado que detecta, em tempo real, a palavra **"socorro"** gritada,
falada ou sussurrada, num ESP32 com microfone I2S INMP441, usando FreeRTOS com
três tarefas concorrentes e um modelo de *keyword spotting* (KWS) pré-treinado.

**Justificativa prática:** detecção de pedido de socorro é uma anomalia acústica
de alto valor — monitoramento de idosos, segurança pessoal, ambientes de risco.
Encaixa no exemplo "grito/alarme: vozes altas em ambiente monitorado" do enunciado.

## 2. Arquitetura RTOS (FreeRTOS)

Três tarefas com prioridades decrescentes, como pede o enunciado:

| Tarefa | Prioridade | Core | Função |
|--------|-----------|------|--------|
| **T1 Captura** | ALTA (5) | 0 | Lê blocos I2S (~62 ms) e preenche o **buffer circular** |
| **T2 Features** | MÉDIA (3) | 1 | Janela de 1 s → **RMS** (gate) → **MFCC** (49×16) → fila |
| **T3 Detecção** | BAIXA (2) | 1 | Modelo TFLite Micro → threshold + debounce → alerta LED/buzzer |

**Sincronização e concorrência:**
- `ringMutex` (**mutex**): protege o buffer circular. T1 escreve, T2 lê; a seção
  crítica é curta (só a cópia da janela) para não bloquear a captura.
- `blockSem` (**semáforo binário**): T1 sinaliza a T2 que chegou um bloco novo,
  evitando *busy-wait* — T2 dorme até haver dados.
- `featQueue` (**fila**, 4 itens): T2 envia as features a T3, desacoplando o
  tempo de inferência do tempo de captura. Se a fila enche, o item é descartado
  (degradação graciosa em vez de travar a captura).
- **Preempção por prioridade**: a captura (T1) nunca perde amostra, pois preempta
  T2/T3. A inferência (T3), mais pesada e menos urgente, roda na menor prioridade.

Diagrama: [`diagrama_rtos.svg`](diagrama_rtos.svg).

## 3. Pipeline de features (idêntico treino ↔ dispositivo)

`config.h` no firmware espelha `projeto/src/common.py`:

- Áudio: 16 kHz, mono, janela de decisão de **1 s** (16000 amostras).
- Frames: janela Hann de 30 ms (480), passo de 20 ms (320) → **49 frames**.
- FFT 512 → **mel filterbank** de 40 bandas (20–8000 Hz) → log.
- **DCT-II** ortonormal → **16 MFCC** por frame.
- Normalização: pico → 0.95 (invariância a volume) + **normalização GLOBAL fixa**
  (média/desvio por-canal calculados no treino e congelados em `feat_norm.h`).
  Substituiu a normalização por-utterance, que amplificava ruído/silêncio e causava
  probabilidades erráticas — é determinística e idêntica em treino e no ESP32.
- **RMS gate** (0.005): abaixo disso é fundo/silêncio e nem classifica — a feature
  RMS pedida no enunciado atua como primeiro filtro barato.

## 4. Modelo e treino

- **Rede**: CNN 2D pequena sobre MFCC (Conv16→Conv32→Conv48 + GAP + Dense), com
  `SpecAugment`, **label smoothing (0.1)** e **weight decay (L2 1e-4)** — calibram a
  saída e reduzem overfitting (probabilidades mais estáveis). ~30 KB quantizada int8.
- **Robustez a entonação**: pitch-shift SIMÉTRICO (±3 semitons) em positivos E
  negativos — dá robustez a tons diferentes sem ensinar "agudo=socorro". Recall sob
  pitch ±3 subiu de ~33–43/71 para ~61–67/71.
- **Validação k-fold (5 dobras)** — melhoria medida com rigor após o pacote
  (normalização-global + rótulos-corrigidos + calibração + pitch simétrico):
  AUC 0.977±0.010 → **0.983±0.004**; F1 0.782±**0.105** → **0.834±0.039**
  (pior dobra 0.58 → 0.81). Ganho de média E, sobretudo, de **estabilidade** (variância ~3× menor).
- **Formatos**: `socorro.onnx` (entregável), `socorro_int8.tflite` e
  `socorro_model_data.h` (C array embarcado).
- **Dataset** (`projeto/dataset/`): ~270 positivos (gritos de amigos por celular +
  gravações do dono em tom normal/sussurro/grito) e >1000 negativos:
  ruído sintético, **ruído real do microfone**, fala PT minerada de áudios longos,
  outras palavras (Speech Commands), **palavras parecidas** ("corro", "controle",
  "socorrista"→"corro"), **fala em voz erguida** e **conversa contínua real**.
- **Augmentation**: time-shift, time-stretch, reverb, mistura de ruído (SNR variado).
  *Pitch-shift aplicado só em negativos* (ensina que voz aguda ≠ socorro; ver §7).
- **Rotulagem**: por intenção do usuário — todo áudio gravado como socorro é
  positivo, mesmo que a transcrição automática (whisper) erre o grito. O whisper
  foi usado só para conferência/mineração, nunca para excluir positivos.

## 5. Resultados (held-out)

| Métrica | Valor |
|---------|-------|
| AUC | ~0.98 |
| Precisão | ~0.90 |
| Recall | ~0.90 |
| Recall socorro (dono, tom normal/sussurro) | ~95–100% |
| Recall socorro (amigos, grito) | ~85% |
| Falsos positivos em ruído do mic | ~0% |

Operação congelada (demo/dispositivo): **threshold 0.70**, **debounce de 3 janelas**
(~190 ms sustentados), passo de 62 ms. Com isso, na validação: socorro dispara e
conversa **não** alarma (0 alertas em ~50 s de conversa).

**Nota de estabilidade:** augmentation muito agressiva (ruído/eco/variações de voz)
deixava as probabilidades erráticas (saltos 0→0.9). A versão final usa augmentation
**conservadora** (deslocamento pequeno + ruído leve) e **sem** variações de voz
sintéticas no treino — fronteira mais estável, ao custo de menos robustez a vozes
muito agudas (que só dados reais de mais vozes resolvem de vez).

## 6. Análise de latência

Medida no firmware (`micros()`), reportada via Serial:

| Etapa | Latência típica* | Onde é medida |
|-------|------------------|---------------|
| Captura de 1 bloco I2S (62 ms) | ~62 ms (limite do áudio) | T1 |
| Extração MFCC (49 frames, FFT 512) | dezenas de ms | `[T2] MFCC latencia` |
| Inferência TFLM int8 | poucos ms | `[T3] inferencia latencia` |
| **Ponta-a-ponta (captura→alerta)** | ~fração de s | `[T3] latencia ponta-a-ponta` |

\* Valores exatos dependem do clock do ESP32; o firmware imprime os máximos reais
observados em execução. No PC, a inferência ONNX medida foi **~2 ms/janela**.

## 7. Discussão e limitações (honesto)

- **Voz feminina / agudos**: o dataset não tem positivos de voz feminina. Tentar
  simular via pitch-shift nos positivos fazia o modelo confundir "agudo" com
  "socorro". A solução adotada — pitch-shift **nos negativos** — reduz o falso
  positivo em voz aguda, mas **não** garante recall em socorro feminino real.
  *Fix definitivo: coletar positivos de várias vozes, incluindo femininas.*
- **Gangorra precisão×recall**: classes se sobrepõem acusticamente (socorro gritado
  vs. fala animada/aguda; sussurro vs. ruído). Com dados limitados, ajustes trocam
  um erro por outro; o ponto congelado é um compromisso, com o **debounce temporal**
  fazendo o trabalho pesado de rejeição.
- **Paridade de MFCC**: a librosa usa `center=True`; o firmware usa framing simples.
  É a principal diferença numérica treino↔dispositivo e deve ser calibrada antes de
  produção (comparar MFCC do C vs. da librosa no mesmo WAV).
- **Sussurro**: energia ≈ ruído; o gate de RMS foi baixado para deixá-lo passar, o
  que aumenta a dependência do modelo para separar sussurro de fundo.

## 8. Reprodutibilidade

Pipeline em `projeto/src/` (ver README): `01`→`04` preparam dados, `05` treina,
`06` exporta ONNX/TFLite/C array. `demo_mic.py` roda a detecção ao vivo no PC
(espelha a lógica do firmware). `retrain.sh` re-treina de ponta a ponta.
