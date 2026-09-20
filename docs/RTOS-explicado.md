# RTOS explicado (para a ponderada) — do zero, com o nosso projeto

Este documento te ensina o que você precisa saber de **RTOS / FreeRTOS** para
entender e apresentar o projeto. Linguagem simples, com o nosso código de exemplo.

---

## 1. O que é um RTOS?

**RTOS = Real-Time Operating System** (sistema operacional de tempo real). É um
"mini sistema operacional" que roda dentro do microcontrolador (o ESP32) e permite
executar **várias tarefas ao mesmo tempo**, decidindo **quem roda e quando**, com
garantias de tempo (as coisas urgentes acontecem na hora).

O ESP32 já vem com o **FreeRTOS** embutido. No Arduino, quando você usa
`xTaskCreate...`, está criando tarefas do FreeRTOS.

> Analogia: um RTOS é o **gerente de uma cozinha**. Vários cozinheiros (tarefas)
> trabalham juntos; o gerente decide quem usa o fogão agora, quem espera, e garante
> que o pedido urgente saia primeiro.

## 2. Por que usar RTOS aqui? (o problema)

Nosso detector precisa fazer 3 coisas **ao mesmo tempo, o tempo todo**:
1. **Capturar áudio** do microfone sem parar (se parar, perde som).
2. **Calcular as features** (MFCC) de cada trecho.
3. **Rodar o modelo** e decidir se é socorro.

Se fizéssemos tudo em um laço só (`loop()`), enquanto o modelo "pensa" (passo 3),
o microfone ficaria **sem ser lido** e perderíamos áudio. O RTOS resolve isso
rodando as três em paralelo, com **prioridades**.

## 3. Tarefa (Task)

Uma **tarefa** é uma função que roda "sozinha", em paralelo com as outras, num
laço infinito. No nosso código:

```cpp
xTaskCreatePinnedToCore(CaptureTask, "capture", 4096, NULL, 5, NULL, 0);
//                       função      nome       pilha       prioridade  core
```
- **função**: o código da tarefa (ex.: `CaptureTask`).
- **pilha (stack)**: memória que a tarefa usa (4096 bytes).
- **prioridade**: número maior = mais importante (roda antes).
- **core**: o ESP32 tem 2 núcleos (0 e 1); dá pra fixar a tarefa num deles.

Nossas 4 tarefas:

| Tarefa | Prioridade | O que faz |
|--------|-----------|-----------|
| `CaptureTask` | **5 (alta)** | lê o microfone (I2S) e enche o buffer circular |
| `FeatureTask` | **3 (média)** | pega 1 s de áudio, calcula RMS + MFCC, manda pra fila |
| `DetectTask` | **2 (baixa)** | roda o modelo, decide, ativa o alerta |
| `AlertTask` | **1 (mínima)** | pisca o LED vermelho e liga pra "polícia" |

## 4. Prioridade e preempção (o coração do "tempo real")

O escalonador do FreeRTOS sempre roda a tarefa **de maior prioridade que está
pronta**. Se uma tarefa mais importante fica pronta, ela **interrompe** (preempta)
a menos importante. Isso se chama **preempção**.

No nosso caso: a **captura (prioridade 5)** sempre tem preferência. Mesmo que o
modelo esteja "pensando" (prioridade 2), a captura o interrompe para ler o
microfone — então **nunca perdemos áudio**. A decisão, mais pesada e menos urgente,
roda na prioridade mais baixa, "nas horas vagas".

## 5. Como as tarefas conversam sem se atrapalhar (concorrência)

Quando várias tarefas mexem nos mesmos dados, dá **bagunça** (condição de corrida:
uma escreve enquanto a outra lê pela metade). O FreeRTOS oferece 3 ferramentas —
e usamos as três:

### 🔒 Mutex (exclusão mútua) — `ringMutex`
O **buffer circular** é compartilhado: a `CaptureTask` escreve, a `FeatureTask` lê.
O **mutex** é uma "chave única": só quem tem a chave mexe no buffer; a outra espera.
Assim nunca leem/escrevem ao mesmo tempo.
```cpp
xSemaphoreTake(ringMutex, portMAX_DELAY);   // pega a chave
... copia a janela de 1 s ...               // seção crítica (curta!)
xSemaphoreGive(ringMutex);                   // devolve a chave
```
> Mantemos a seção crítica **curta** (só a cópia) pra não travar a captura.

### 🚦 Semáforo — `blockSem`
Como a `FeatureTask` sabe que chegou áudio novo? Em vez de ficar perguntando
"chegou? chegou?" (desperdiça CPU), ela **dorme** até a `CaptureTask` dar um sinal.
O **semáforo** é esse sinal ("sinal verde").
```cpp
// CaptureTask, ao encher um bloco:
xSemaphoreGive(blockSem);        // avisa: "tem áudio novo!"
// FeatureTask:
xSemaphoreTake(blockSem, portMAX_DELAY);   // dorme até haver sinal
```

### 📮 Fila (Queue) — `featQueue`
A `FeatureTask` calcula as features e coloca numa **fila**; a `DetectTask` tira da
fila quando puder. A fila **desacopla** as duas: a extração não precisa esperar o
modelo terminar. Se a fila enche, o item mais novo é descartado (o sistema não trava).
```cpp
xQueueSend(featQueue, &feat, 0);            // FeatureTask envia
xQueueReceive(featQueue, &feat, portMAX_DELAY);  // DetectTask recebe
```

> Resumo com a analogia da cozinha: **mutex** = uma comanda por vez; **semáforo** =
> a campainha "pedido novo!"; **fila** = o balcão de pratos prontos esperando entrega.

## 6. Diagrama

Veja [`diagrama_rtos.svg`](diagrama_rtos.svg): mostra as 4 tarefas, o buffer, o
mutex, o semáforo e a fila, com as setas de quem fala com quem.

## 7. Perguntas típicas da banca (com resposta)

- **"O que é uma tarefa no FreeRTOS?"** Uma função que roda em paralelo, em laço
  infinito, escalonada por prioridade.
- **"Por que prioridades diferentes?"** Pra garantir que o urgente (captura) nunca
  seja atrasado pelo pesado (inferência). É o requisito de tempo real.
- **"O que é preempção?"** O escalonador interromper uma tarefa de baixa prioridade
  para rodar uma de alta que ficou pronta.
- **"Como você evita condição de corrida?"** Mutex protegendo o buffer circular
  (seção crítica curta) + fila entre extração e detecção.
- **"Diferença entre mutex e semáforo?"** Mutex protege um recurso (só um dono por
  vez); semáforo sinaliza/sincroniza eventos entre tarefas (produtor→consumidor).
- **"E se a fila encher?"** Descartamos o item (degradação graciosa) — melhor perder
  uma janela do que travar a captura.
- **"Por que 2 cores?"** Fixamos a captura no core 0 e o resto no core 1, separando
  a E/S do processamento.

## 8. Onde ver no código
Tudo em [`../esp32/socorro_detector.ino`](../esp32/socorro_detector.ino):
`CaptureTask`, `FeatureTask`, `DetectTask`, `AlertTask`, e a criação delas +
`ringMutex`, `blockSem`, `featQueue` no `setup()`.
