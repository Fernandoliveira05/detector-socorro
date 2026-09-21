# Passo a passo da Ponderada — Detector de "socorro" no ESP32

> Guia pra **eu explicar** o projeto. Dois focos fortes: **RTOS/concorrência** e **o modelo**.
> Tudo roda **na borda** (no próprio ESP32): o áudio nunca sai do dispositivo — só o *evento* de alerta.

---

## 0. A ideia em uma frase

Um **ESP32 + microfone INMP441** que escuta o ambiente em tempo real, reconhece a palavra **"socorro"** com uma rede neural embarcada, e ao detectar **acende um LED vermelho, toca o buzzer e liga para a emergência (Twilio)** — coordenando tudo com **FreeRTOS** em 4 tarefas paralelas.

Cadeia mental:

```
🎙 Ouvir  ──►  🔢 Resumir  ──►  🧠 Decidir  ──►  🚨 Alertar
 I2S/mic       MFCC 49×16      CNN int8 (TFLM)   LED + buzzer + ligação
```

---

## 1. Visão geral do fluxo (o que fizemos, em ordem)

1. **Coletamos áudio** de "socorro" (meu e de amigos) em vários tons/volumes + uma montanha de **negativos** (ruído, conversa, palavras parecidas).
2. **Extraímos features (MFCC)** de cada clipe de 1 s — a "impressão digital" sonora.
3. **Treinamos uma CNN pequena** para dizer *socorro* vs *não-socorro*.
4. **Quantizamos para int8 e exportamos** um array C (~30 KB) que cabe no ESP32.
5. **Escrevemos o firmware** com **4 tarefas FreeRTOS** sincronizadas (captura → features → detecção → alerta).
6. **Garantimos paridade de features**: o MFCC em C (no chip) dá o mesmo resultado do MFCC em Python (no treino).
7. **Domain adaptation**: gravamos o que o **próprio INMP441** escuta e retreinamos — porque o mic do chip "soa" diferente dos mics em que o modelo aprendeu.
8. **Medimos latência** de cada etapa e disparamos o **alerta + ligação**.

---

## 2. RTOS e concorrência (o coração da ponderada)

### 2.1 Por que precisamos de RTOS aqui

As etapas têm **ritmos e prioridades diferentes** e acontecem **ao mesmo tempo**:

- A **captura** não pode parar nunca (se parar, perdemos amostras de áudio → buracos no som).
- A **extração de MFCC** é pesada (~dezenas de ms de CPU).
- A **inferência** roda quando há features novas.
- O **alerta** (piscar LED, tocar buzzer, ligar) não pode travar as outras.

Se fizéssemos tudo em um `loop()` sequencial, o MFCC ou a ligação **bloqueariam** a captura e o áudio ficaria cheio de falhas. O RTOS resolve isso com **tarefas concorrentes, prioridades e preempção**, e os **dois núcleos** do ESP32.

### 2.2 As 4 tarefas

| Tarefa | Prioridade | Núcleo | O que faz |
|---|---|---|---|
| **T1 · CaptureTask** | 5 (alta) | 0 | Lê o I2S em blocos de 256 amostras e escreve no **buffer circular**. |
| **T2 · FeatureTask** | 3 (média) | 1 | A cada ~125 ms, pega 1 s do buffer, calcula **RMS + MFCC** e põe na **fila**. |
| **T3 · DetectTask** | 2 (baixa) | 0 | Tira features da fila, roda o **modelo int8**, aplica **threshold + debounce**. |
| **T4 · AlertTask** | 1 (mais baixa) | 0 | Enquanto o alerta está ativo: pisca LED, toca buzzer e **liga pra polícia**. |

> O enunciado pede **≥ 3 tarefas sincronizadas** — temos **4**.

**Prioridades**: captura é a mais alta porque é a que tem *deadline* rígido (o hardware I2S entrega amostras num ritmo fixo; se não lermos, o buffer DMA transborda). A detecção e o alerta são mais baixas porque toleram um atraso de alguns ms.

**Preempção**: se a T2 estiver no meio de um MFCC e chegar áudio novo, o escalonador **interrompe** a T2 pra rodar a T1 (mais prioritária), e depois volta pra T2. É isso que garante que a captura nunca "perde a hora".

### 2.3 Os 3 mecanismos de sincronização

Aqui está o núcleo do "resolver conflitos de concorrência":

**a) `ringMutex` (mutex) — protege o buffer circular**
- T1 **escreve** no `ring[]` e T2 **lê**. Sem proteção, T2 poderia ler enquanto T1 escreve o mesmo índice → dado corrompido (*race condition*).
- O mutex garante **exclusão mútua**: enquanto um mexe no índice de escrita (`writeIdx`), o outro espera.
- A seção crítica é **curtíssima** (só ler/atualizar o índice) — não seguramos o mutex durante o MFCC inteiro, senão a captura travaria.

**b) `blockSem` (semáforo binário) — sinaliza "tem áudio novo"**
- A T1 dá `xSemaphoreGive(blockSem)` a cada `STEP_SAMPLES` (~125 ms).
- A T2 fica **bloqueada** em `xSemaphoreTake(blockSem)` sem gastar CPU até haver bloco novo.
- Isso é **produtor–consumidor**: a T2 só acorda quando faz sentido, em vez de ficar "perguntando" (polling) e desperdiçando CPU.

**c) `featQueue` (fila) — passa as features de T2 → T3**
- A T2 empacota o vetor MFCC (49×16) num `Feature` e faz `xQueueSend`.
- A T3 faz `xQueueReceive`. A fila **desacopla** as duas: se a inferência atrasar um pouco, as features ficam enfileiradas (profundidade 4) em vez de se perderem.
- Se a fila enche, descartamos a mais nova (tempo real: melhor perder um frame do que acumular atraso).

**d) `alertUntil` / `lastProb` (estado T3 → T4)**
- A T3 só marca "alerta ativo até o instante X". A T4 lê esse estado e cuida do LED/buzzer/ligação. Assim a **detecção não fica presa** esperando o buzzer tocar ou a ligação completar.

### 2.4 Uso dos dois núcleos (dual-core)

- **Núcleo 1**: só a **FeatureTask** (o MFCC é o trabalho mais pesado — roda sozinho, sem disputar CPU).
- **Núcleo 0**: **Captura + Detecção + Alerta** (tarefas mais leves ou que bloqueiam esperando I/O).

Isso equilibra a carga: o MFCC pesado não atrapalha a captura e vice-versa.

### 2.5 O bug de concorrência que resolvemos (bom pra contar)

No começo a **DetectTask monopolizava o núcleo 0** e o **watchdog** do FreeRTOS reiniciava o chip (`task_wdt: IDLE0`). Duas correções:
1. `vTaskDelay(pdMS_TO_TICKS(5))` no fim da T3 → ela **cede a CPU** de tempos em tempos (alimenta o watchdog).
2. Reorganizamos os núcleos (MFCC sozinho no núcleo 1).

Isso é um exemplo real de **starvation** (uma tarefa faminta impedindo as outras) e de como o RTOS exige *ceder a CPU* de forma cooperativa quando não há bloqueio natural.

### 2.6 Latência (o enunciado pede medir cada etapa)

Medimos com `micros()` dentro das tarefas e imprimimos no Serial:
- **T2**: latência do MFCC (`[T2] MFCC latencia max: ... us`).
- **T3**: latência da inferência (`[T3] inferencia latencia max: ... us`).
- **Ponta-a-ponta**: do instante da captura até disparar o alerta (`latencia ponta-a-ponta`), usando o timestamp `t_capture_us` que viaja junto na fila.

---

## 3. O modelo (pega firme aqui)

### 3.1 O problema de ML

É **keyword spotting** (detecção de palavra-chave): classificação binária de janelas de **1 segundo** de áudio em *socorro* (1) vs *não-socorro* (0). O desafio real **não** é acertar meu "socorro" — é:
- **generalizar** para vozes, tons (grito/normal/sussurro) e volumes diferentes;
- **não disparar** com barulho, conversa ou palavras parecidas ("corro", "socorrista", "controle");
- **caber e rodar em tempo real** num microcontrolador.

### 3.2 Features: por que MFCC (e não a onda crua)

A forma de onda tem 16.000 números por segundo — caro e sem estrutura pra uma rede pequena. Os **MFCC** resumem *como a energia se distribui nas frequências* de um jeito parecido com a audição humana. Nosso pipeline (idêntico no treino em Python e no firmware em C):

| Parâmetro | Valor | Sentido |
|---|---|---|
| Janela | 30 ms (480 amostras) | trecho curto ~estacionário |
| Passo (hop) | 20 ms (320 amostras) | sobreposição entre frames |
| FFT | 512 pontos | espectro do frame |
| Filtros mel | 40 | agrupa frequências como o ouvido |
| Coef. MFCC | 16 | resumo compacto |
| Frames | 49 | 1 + (16000−480)/320 |

Resultado: uma "imagem" **49 × 16** que entra na CNN. Ainda aplicamos:
- **normalização de pico (0.95)** por clipe → robustez a volume;
- **log natural** da energia mel;
- **DCT-II ortonormal** → coeficientes MFCC;
- **normalização global fixa** (média/desvio calculados **só no treino**) → probabilidades **estáveis** (sem saltos 0→0.9 à toa).

### 3.3 Paridade Python ↔ C (detalhe que dá credibilidade)

O treino é em Python (`librosa`) e o chip roda C (`features.cpp`, FFT feita à mão). Se os MFCC não baterem, o modelo vê "outra coisa" no chip. Então **reescrevemos o MFCC em Python pra replicar exatamente o C** (mesma janela de Hann periódica, FFT512, triângulos mel crus, log natural, DCT-II ortho, mesma normalização global) e **provamos numericamente** que batem: diferença máxima ~**0.0003**. Por isso o que funciona no PC funciona no chip.

### 3.4 A rede (CNN pequena)

```
Entrada  49 × 16 × 1  (MFCC)
 → Conv2D(16, 3×3) + BatchNorm + MaxPool
 → Conv2D(32, 3×3) + BatchNorm + MaxPool
 → Conv2D(48, 3×3) + BatchNorm
 → GlobalAveragePooling2D            (resume o mapa inteiro num vetor)
 → Dense(48, relu) + Dropout(0.3)
 → Dense(2, softmax)                 (prob de [não-socorro, socorro])
```

Escolhas e por quê:
- **Convoluções** capturam padrões tempo-frequência (a "assinatura" do socorro) independentemente de *onde* na janela ele aparece.
- **GlobalAveragePooling** em vez de Flatten → **muito menos parâmetros** (essencial pra caber no chip) e menos overfitting.
- **Dropout 0.3 + L2 + label smoothing 0.1** → regularização, evita decorar as vozes do treino.
- Treino: Adam (1e-3), 80 épocas com **EarlyStopping** (paciência 12) na *val_loss*.

### 3.5 Dados: onde mora a real dificuldade

O trabalho pesado foi montar um dataset honesto. Hoje: **~516 positivos** e **~1.670 negativos** em várias categorias:
- **positivos**: socorro em grito/normal/sussurro, meus e de amigos;
- **negativos**: ruído, silêncio, conversa (`conversation`, `pt_speech`), **fala alta genérica** (`loud_speech`, pra ele não achar que "alto = socorro"), e **palavras parecidas** (`other_words`: "corro", "socorrista"…).

Aprendizados (contam bem a jornada):
- **Sem `loud_speech`**, o modelo disparava com qualquer tom mais alto. Com ela, aprendeu que o gatilho é a **palavra**, não o **volume**.
- **Pitch shift simétrico (±3 semitons) em positivos E negativos** → robustez a vozes agudas/graves **sem** ensinar "agudo = socorro".
- **Augmentation conservadora** (shift ±150 ms, ruído leve, ganho suave). Reverb/time-stretch pesados deixavam as probabilidades erráticas — tiramos.
- **Split por arquivo** (não por janela) pra não vazar o mesmo áudio entre treino e teste.
- **Boost in-domain moderado (2×)** pra dados do mic; um boost alto (6×) enviesava demais pra minha voz.

### 3.6 Decisão: threshold + debounce

A CNN dá uma probabilidade `p`. Pra virar alerta:
- **`THRESHOLD = 0.55`**: acima disso, "candidato a socorro".
- **`CONSEC = 3`**: precisa de **3 janelas seguidas** acima do limiar (~375 ms sustentados) → mata disparos de um frame isolado (ruído/pico).
- **`RMS_GATE`**: se o trecho é silêncio/fundo, nem chama o modelo (economia + menos falso-positivo).

### 3.7 Quantização (por que int8)

Treinamos em float32, mas exportamos em **int8** (TFLite Micro): pesos e ativações viram inteiros de 8 bits. Ganho: modelo de **~30 KB**, inferência rápida e sem unidade de ponto flutuante pesada. A T3 **quantiza** a entrada (usando escala/zero-point do tensor) antes do `Invoke()` e **dequantiza** a saída pra ler a probabilidade.

### 3.8 Domain adaptation — o que destravou o chip (história forte)

No PC o modelo ia muito bem, mas **no chip não detectava** (`p ≈ 0.02`). Diagnóstico: **domain shift** — o modelo aprendeu com áudio de celular/mic de PC e **nunca tinha ouvido o INMP441**, que tem timbre/ruído próprios.

A solução:
1. Pusemos um **modo de gravação** no firmware (`DUMP_AUDIO`) que **transmite pela serial o áudio cru que o INMP441 escuta** (int16, 16 kHz, 921600 baud).
2. Gravamos "socorro" **pelo próprio mic do projeto** e reconstruímos os WAVs no PC.
3. **Diagnóstico numérico**: o modelo antigo acertava 4 de 7 gravações; as 2 que falhavam eram **áudio saturado** (grito colado no mic → distorção).
4. **Retreinamos** incluindo essas gravações do INMP441 (inclusive as saturadas).

Resultado medido depois:
- **INMP441: p = 0,99–1,00 nas 7 gravações** (antes: 0,02–0,03 nas que falhavam);
- **sem regressão**: 95% dos positivos originais mantidos;
- **0% de falso-positivo** nos negativos.

Moral: em edge ML, **o modelo precisa treinar com o sensor real**. Foi o que fez funcionar no chip.

---

## 4. Alerta e notificação (fecha o caso de uso)

Ao confirmar socorro, a T4:
- **pisca o LED vermelho** e **toca o buzzer** (alerta local imediato);
- **liga via Twilio** (uma vez, com cooldown de 30 s) tocando uma mensagem tipo *"este número está pedindo emergência na rua tal"*;
- só o **evento** sai do dispositivo — **o áudio nunca é enviado** (privacidade + banda).

---

## 5. Checklist do enunciado (pra bater na hora da defesa)

| Pedido | Como atendemos |
|---|---|
| Captura via ESP32 + INMP441 | T1 CaptureTask (I2S, buffer circular) |
| Modelo pré-treinado detectando o som | CNN int8 (TFLite Micro) embarcada |
| RTOS com ≥ 3 tarefas sincronizadas | **4 tarefas** + mutex + semáforo + fila |
| Conflitos de concorrência resolvidos | `ringMutex` (buffer), `blockSem` (produtor-consumidor), `featQueue` (desacople) |
| Latência de cada etapa medida | `micros()` em T2/T3 + ponta-a-ponta no Serial |
| Alerta por LED/buzzer | T4 AlertTask (LED vermelho + buzzer) |
| Modelo `.onnx` + diagrama RTOS + relatório | em `treino/modelos/` e `docs/` |
| Código de teste (simula + mede performance) | `treino/testar.py` |

---

## 6. Perguntas que podem me fazer (e a resposta curta)

- **"Por que mutex no buffer mas fila nas features?"** O buffer é **memória compartilhada** de acesso concorrente → mutex. As features são um **fluxo de mensagens** de uma tarefa pra outra → fila desacopla e tolera atraso.
- **"E se duas tarefas quiserem o buffer ao mesmo tempo?"** O mutex serializa; como a seção crítica é mínima (só o índice), a espera é desprezível.
- **"Por que 4 tarefas e não uma só?"** Ritmos e prioridades diferentes; separar evita que o MFCC/ligação bloqueiem a captura (deadline rígido).
- **"Por que não mandar o áudio pra nuvem?"** Latência, banda e privacidade. Tudo decide na borda; só o alerta sai.
- **"Por que o modelo não funcionava no chip e agora funciona?"** *Domain shift*: retreinamos com áudio do próprio INMP441 (domain adaptation).
- **"Como garante que não dispara com qualquer barulho?"** Negativos de fala alta + palavras parecidas, threshold **e** debounce de 3 janelas, gate de RMS.
