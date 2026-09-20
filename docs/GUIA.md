# 🗣️ Guia pra entender e explicar o projeto (ponderada)

Este guia é em português simples, pra você **entender o processo** e conseguir
**explicar na demonstração**. Nada de jargão sem tradução.

---

## 1. O que o projeto faz (em 1 frase)

Um ESP32 com microfone ouve o ambiente o tempo todo e **acende um LED / toca um
buzzer quando alguém grita "socorro"** — sem internet, tudo processado no próprio chip.

## 2. A ideia central em 3 passos

Pensa numa linha de produção com 3 estações:

1. **Ouvir** 🎙️ — o microfone capta o som e guarda o último 1 segundo.
2. **Resumir** 🔢 — transformamos esse 1s de som numa "impressão digital" de números (MFCC).
3. **Decidir** 🧠 — um mini cérebro (rede neural) olha a impressão digital e diz:
   "isso é socorro?" com uma probabilidade de 0 a 1.

Se a probabilidade fica alta por tempo suficiente → **alarme**.

## 3. O que é MFCC (a "impressão digital do som")

Nosso ouvido não escuta a onda crua; escuta **quais frequências** têm em cada momento.
O MFCC faz isso com o áudio: quebra o 1 segundo em ~49 fatias de tempo e, pra cada
fatia, resume "quanta energia tem em cada faixa de tom" em 16 números. Resultado:
uma tabela **49 × 16** que descreve o som de um jeito parecido com o ouvido humano.
A rede neural aprende a reconhecer o "desenho" que a palavra socorro faz nessa tabela.

> Analogia: é como transformar uma música num espectrograma/"equalizador" e a rede
> aprende o formato visual da palavra socorro.

## 4. Como o modelo aprendeu (dados)

Um detector de palavra precisa de dois tipos de exemplo:

- **POSITIVOS** = gente falando "socorro" (você, amigos, tons variados: grito,
  normal, sussurro). ~270 exemplos.
- **NEGATIVOS** = tudo que **não** é socorro, e quanto mais parecido, melhor:
  ruído, silêncio, conversa normal, **gritos de outras palavras**, **palavras
  parecidas** ("corro", "controle"), ruído do próprio microfone. >1000 exemplos.

**Por que tantos negativos?** Porque o erro perigoso é o modelo achar que *qualquer*
som alto é socorro. Mostrando muitos "quase-socorros" que **não** são, ele aprende a
focar na palavra, não no volume.

Também usamos **aumento de dados**: pegamos cada exemplo e criamos variações (com
ruído, eco, mais rápido/devagar) pra o modelo aguentar o mundo real com poucos áudios.

**Variação de voz (3 versões por áudio):** criamos automaticamente uma versão
grave, uma aguda e uma "arrastada" de cada áudio (deslocando pitch+formantes,
como pessoas de tamanhos diferentes). Duas travas importantes que aprendemos:
1. **Simetria** — fazemos isso tanto no socorro quanto nas palavras negativas.
   Assim o modelo aprende *a palavra*, não *o tom* (se só o socorro ficasse agudo,
   ele passaria a achar que "qualquer voz aguda = socorro" — foi um erro que tivemos
   e corrigimos exatamente com essa simetria).
2. **Sem vazamento** — as variações entram só no treino; validação e teste usam
   áudios reais originais, pra a acurácia não mentir.

## 5. A arquitetura RTOS (o coração da ponderada)

O ESP32 faz 3 coisas **ao mesmo tempo**, e o FreeRTOS organiza isso em 3 **tarefas**
com prioridades diferentes (quem é mais urgente roda primeiro):

| Tarefa | Prioridade | O que faz |
|--------|-----------|-----------|
| **T1 Captura** | ALTA | lê o microfone sem parar e guarda no buffer circular |
| **T2 Features** | MÉDIA | pega 1s, calcula RMS e MFCC, manda pra fila |
| **T3 Detecção** | BAIXA | roda o modelo e decide se alarma |

**Por que essas prioridades?** Perder áudio é o pior — então a captura é a mais
urgente. A decisão é pesada mas pode esperar um tiquinho → prioridade baixa.

**Como elas conversam sem se atrapalhar (concorrência):**
- 🔒 **Mutex** (`ringMutex`): o buffer circular é como um caderno compartilhado.
  O mutex é a "caneta única" — só uma tarefa escreve/lê por vez, evitando bagunça.
- 🚦 **Semáforo** (`blockSem`): a T1 dá um "sinal verde" quando chega áudio novo,
  então a T2 **dorme** até ter trabalho (não fica gastando CPU perguntando "chegou?").
- 📮 **Fila** (`featQueue`): a T2 deixa as features numa "caixa de correio" e a T3
  pega quando puder. Assim a T2 não trava esperando a T3 terminar de pensar.

> Analogia: T1 é o garçom anotando pedidos (rápido), T2 é a cozinha preparando,
> T3 é a entrega. Mutex = uma comanda por vez; fila = balcão de pratos prontos;
> semáforo = a campainha que avisa "pedido novo!".

## 6. Como demonstrar na hora

```bash
cd "/Users/fsoaresdeoliveira/Downloads/Audios - Amigos Pedindo Socorro"
source _work/venv/bin/activate

python projeto/pipeline.py explicar      # mostra o mapa do processo
python projeto/src/demo_mic.py           # detecção AO VIVO (grite socorro!)
python projeto/src/test_performance.py   # acurácia + latência
```
O firmware do ESP32 está em `projeto/firmware/socorro_detector/` (C++).

## 7. Perguntas prováveis do checkpoint (com resposta curta)

- **"Por que 3 tarefas e não uma só?"** Pra não perder áudio: captura tem que ser
  ininterrupta; separar por prioridade garante que o trabalho pesado (modelo) não
  atrapalhe a captura. É o requisito de concorrência do RTOS.
- **"Como evita condição de corrida no buffer?"** Mutex na seção crítica (a cópia
  da janela é curta) + fila entre features e detecção.
- **"Que features usa?"** RMS (energia, também serve de 'gate' pra ignorar silêncio)
  e MFCC (16 coef × 49 frames).
- **"Como o modelo roda no ESP32?"** Rede treinada em Python, quantizada pra int8 e
  embarcada como C array; roda com TensorFlow Lite Micro.
- **"Qual a latência?"** Inferência ~ poucos ms; o firmware imprime a latência real
  ponta-a-ponta (captura→alerta) via Serial.
- **"E os falsos positivos?"** Limiar de 0.70 + **debounce**: só alarma se a detecção
  se sustenta ~190 ms, o que fala/ruído curto não faz.
- **"Por que a augmentation é conservadora?"** Descobrimos que aumento agressivo
  (muito ruído/eco/variações) deixava as probabilidades instáveis (saltavam de 0 a
  0.9 à toa). Menos é mais: augmentation leve deu uma fronteira estável.

## 8. Limitações (fale com honestidade — pega bem)

- Sem vozes femininas nos positivos → socorro feminino tem recall menor.
- Sussurro tem energia parecida com ruído → é o caso mais difícil.
- O MFCC do firmware é uma aproximação do MFCC do treino (librosa) — em produção,
  calibraria os dois pra baterem exatamente.

Detalhes técnicos completos em [`report/relatorio_tecnico.md`](report/relatorio_tecnico.md).
