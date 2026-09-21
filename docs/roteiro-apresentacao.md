# Roteiro da apresentação — SOS-ESP

> Detector acústico de "socorro" · Ponderada · Sistemas Embarcados + Edge ML
> **Slides no Figma:** https://www.figma.com/slides/cyDWD3R0GByOcCasfNQ2Wz
> Duração alvo: **4 a 5 minutos** + perguntas. 8 slides, 4 seções.

---

## Como apresentar (o essencial)

- **Você é o protagonista, não os slides.** Cada slide tem pouco texto de propósito: é pano de fundo pra sua fala, não legenda pra ler. Nunca leia o slide em voz alta.
- **A onda ciano é o fio da apresentação.** Ela atravessa todos os slides e muda de estado: calma quando escuta, vira um pico vermelho na demo. Se travar, olhe pra ela e siga o fio: escutar → decidir → alertar.
- **Ritmo:** comece devagar e pessoal (slides 1–2), acelere no técnico (4–6), respire na demo (7), feche no emocional (8).
- **Silêncio é seu amigo.** Depois da pergunta do slide 3 e no pico da demo, faça pausa. Deixe o slide trabalhar por você.
- As **notas do apresentador** já estão em cada slide no Figma (aparecem no modo Apresentar). Este documento é o mesmo roteiro, ampliado.

---

## Seção 1 — Abertura

### Slide 1 · SOS-ESP (~30s)
- Abra **por você**: "Meu nome é Fernando, nasci em Taboão da Serra."
- Segure 2 segundos no título. Diga o que é em **uma frase**: *"Construí um chip que reconhece a palavra 'socorro' e chama ajuda sozinho."*
- Não explique nada ainda. **Transição:** "Mas por que isso me importa tanto?"

## Seção 2 — A ideia

### Slide 2 · Taboão da Serra (~45s)
- Momento pessoal — **vá devagar, respire.** Conte o medo real: precisar gritar por socorro e não ter ninguém por perto pra ouvir.
- A cidade ao fundo **é Taboão**. Deixe a imagem falar; aqui não tem dado, tem verdade.
- **Transição para a virada:** "E se desse pra resolver isso com uma tecnologia barata?"

### Slide 3 · A ideia (~40s)
- Leia a pergunta e **faça uma pausa** — ela é retórica.
- As três linhas são as promessas do produto: **na borda, em tempo real, privacidade.**
- Enfatize a privacidade: *"o áudio nunca sai do aparelho — só o alerta sai."* Isso é o diferencial.
- O ponto vermelho "ouvindo…" mostra o aparelho já de vigília. **Transição:** "Como isso funciona por dentro?"

## Seção 3 — Como funciona

### Slide 4 · Arquitetura (~45s)
- Percorra a linha da esquerda pra direita: **Ouvir → Resumir → Decidir → Alertar.**
- Traduza: o microfone I2S enche 1 segundo de áudio → o MFCC é a "impressão digital" desse som → uma CNN pequena (int8, TFLite Micro) decide → se for socorro, acende o LED e liga.
- O vermelho só aparece no fim: é o alerta. **Reforce:** "tudo isso dentro do ESP32, nada vai pra nuvem."

### Slide 5 · As amostragens (~45s)
- Diga que **você mesmo gravou** centenas de "socorro" — gritado, falado e sussurrado.
- O segredo são os **negativos**: ruído, conversa e principalmente palavras parecidas (*corro, controle, socorrista*), pra não disparar à toa.
- **0.98 de AUC** é um número honesto, de validação cruzada (k-fold); F1 de 0.86, consistente nos três tons de voz.
- A grade à direita é o MFCC 49×16 visualizado — um espectrograma.

### Slide 6 · RTOS (~60s) — **coração da ponderada**
- Avise que este é o ponto técnico central. **É aqui que a banca vai perguntar.**
- Quatro tarefas rodam em paralelo no FreeRTOS. Aponte a barra cheia da `CaptureTask`: ela tem **prioridade máxima**, então **interrompe (preempta)** as outras e **nunca perde áudio** — esse é o "tempo real".
- Uma frase pra cada primitiva de sincronização:
  - **Mutex** — uma chave: só uma tarefa mexe no buffer por vez.
  - **Semáforo** — sinal verde: avisa que chegou áudio novo.
  - **Fila** — desacopla a extração de features da detecção.

## Seção 4 — Demo & Fecho

### Slide 7 · Demo ao vivo (~60s)
- **Menos fala, mais ação:** rode a demo e grite "socorro".
- Se o hardware falhar (o microfone físico é o ponto frágil), tenha o **backup** pronto — vídeo ou demo no PC — e mencione com naturalidade, sem pedir desculpa.
- Deixe o **pico vermelho** ser o clímax. Não fale por cima do momento.

### Slide 8 · Fecho (~30s)
- **Feche o arco:** volte pra você e pra Taboão — *"um grito que agora tem quem escute."*
- Recap em uma frase: na borda, privado, em tempo real.
- "Obrigado" e **abra para perguntas** com confiança.

---

## Preparação para a banca (perguntas prováveis)

- **O que é uma tarefa no FreeRTOS?** Uma função que roda em paralelo, em laço infinito, escalonada por prioridade.
- **O que é preempção?** O escalonador interromper uma tarefa de baixa prioridade para rodar uma de alta que ficou pronta (no nosso caso, a captura sempre ganha).
- **Mutex vs. semáforo?** Mutex protege um recurso (um dono por vez); semáforo sinaliza um evento entre tarefas (produtor → consumidor).
- **E se a fila encher?** Descartamos a janela mais nova — degradação graciosa; melhor perder uma janela do que travar a captura.
- **Por que MFCC e não o áudio bruto?** Reduz o som a poucas features estáveis que cabem no chip e generalizam melhor.
- **Por que roda tudo na borda?** Latência baixa, funciona sem internet e preserva privacidade (o áudio nunca sai do aparelho).
- **Limitação honesta:** poucos positivos de voz feminina no dataset → recall menor nesse caso; e o microfone físico é o elo frágil do protótipo.

---

## Créditos das fotos (licenças CC — atribuição obrigatória)

As fotos foram tratadas em duotone, mas as licenças CC-BY exigem crédito ao autor:

| Slide | Imagem | Autor | Fonte | Licença |
|---|---|---|---|---|
| 1 | Rua do Comércio à noite (Centro, São Paulo) | Rodrigo Argenton | Wikimedia Commons | CC BY-SA 4.0 |
| 2 | Vista de Taboão da Serra (Grande SP) | Daiane O. Silva | Wikimedia Commons | CC BY-SA 4.0 |

Outras imagens CC baixadas e disponíveis como alternativa (viatura GCM + Smart Sampa/Agência Brasil, viaturas PM-SP, ambulância SAMU 192, Av. 23 de Maio à noite) estão em `.claude/jobs/.../tmp/news/` com manifesto de créditos, caso queira trocar.
