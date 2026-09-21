# 🍳 O restaurante que escuta "socorro"

> A mesma ponderada, contada como se o ESP32 fosse a **cozinha de um restaurante**.
> Ideal pra explicar **RTOS e concorrência** sem ninguém dormir na banca.

---

## O restaurante em uma frase

Imagina um restaurante minúsculo (o ESP32) que só tem **um prato no cardápio**:
detectar a palavra **"socorro"**. O som que entra pela porta é o "ingrediente", e o
"prato pronto" é um **alerta** (LED vermelho + buzzer + ligação pra emergência).

O pulo do gato: são **4 funcionários trabalhando ao mesmo tempo**, cada um no seu
ritmo, sem tropeçar um no outro. Quem organiza esse caos é o **FreeRTOS** — o
*gerente invisível* que decide quem trabalha agora e quem espera a vez.

```
👂 Ouvir  ──►  🔪 Preparar  ──►  👅 Provar  ──►  🚨 Servir o alarme
```

---

## 👥 Os 4 funcionários (as tarefas do RTOS)

| # | Funcionário | Apelido | O que faz o dia inteiro |
|---|---|---|---|
| **T1** | 👂 **O Ouvinte** | *CaptureTask* | Fica coladinho na porta anotando **tudo** que entra de som, sem parar nunca. |
| **T2** | 🔪 **O Cozinheiro** | *FeatureTask* | Pega o último 1 segundo de som e "cozinha" num prato padronizado (o **MFCC**). |
| **T3** | 👅 **O Provador** | *DetectTask* | Prova o prato e decide: "isso é socorro ou não?" (roda a **rede neural**). |
| **T4** | 🚨 **O Gerente** | *AlertTask* | Se for socorro de verdade, aciona o alarme e **liga pra emergência**. |

E tem uma regra de ouro do restaurante — a **ordem de prioridade** quando dá aperto:

> 👂 **O Ouvinte tem prioridade máxima.** Se ele parar de anotar por um segundo,
> o som some pra sempre. Os outros até podem esperar um tiquinho; o Ouvinte, **nunca**.

Por isso o gerente (FreeRTOS) pode **interromper** o Cozinheiro no meio de um prato
pra deixar o Ouvinte anotar, e depois manda o Cozinheiro voltar. Isso se chama
**preempção** — o chefe fura a fila pelo mais urgente.

E como o restaurante tem **duas bancadas** (os 2 núcleos do ESP32), o Cozinheiro
(que dá o trabalho mais pesado) ganha uma **bancada só pra ele**, enquanto os outros
três dividem a outra.

---

## 🤹 Os 3 truques pra ninguém se atropelar (a sincronização)

Aqui mora a alma da ponderada. Com 4 pessoas trabalhando juntas, **três problemas
clássicos** aparecem — e cada um tem um truquezinho de cozinha que resolve.

### 🖊️ Truque 1 — O caderno de uma caneta só (o *mutex*)

O Ouvinte anota o som num **caderno compartilhado** (o buffer circular). O
Cozinheiro lê desse mesmo caderno pra saber o que preparar.

**O perigo:** e se o Cozinheiro tentar ler *exatamente* na hora que o Ouvinte está
escrevendo naquela linha? Ele leria meia palavra, um borrão — informação corrompida.
(No mundo técnico isso é a temida *race condition*.)

**O truque:** existe **uma única caneta**. Quem quer mexer no caderno pega a caneta;
o outro **espera a caneta ficar livre**. Só um por vez. 🖊️

> Detalhe esperto: o Ouvinte pega a caneta, escreve **uma linha rapidinho** e já
> devolve. Ele **não** fica com a caneta na mão o tempo todo — senão o Cozinheiro
> ficaria parado esperando e a cozinha travava.

Nome técnico: **`ringMutex`** (um *mutex* = "exclusão mútua" = a caneta única).

### 🔔 Truque 2 — A campainha "tá pronto!" (o *semáforo*)

O Cozinheiro **não fica perguntando** de 5 em 5 segundos "já tem som novo? já tem?
já tem?" — isso cansaria ele à toa (desperdício de CPU).

**O truque:** o Ouvinte tem uma **campainha**. A cada pedacinho de som novo anotado,
ele toca: *🔔 tá pronto!* O Cozinheiro fica **tranquilo, cochilando**, e só acorda
quando a campainha toca. Aí ele levanta e cozinha.

Isso é o famoso **produtor–consumidor**: um produz (som), o outro consome (vira
prato), e a campainha avisa a hora certa — sem ninguém ficar espiando o outro.

Nome técnico: **`blockSem`** (um *semáforo*).

### 🍽️ Truque 3 — O balcão de pratos prontos (a *fila*)

Quando o Cozinheiro termina um prato (o MFCC), ele **não corre atrás do Provador**
pra entregar na mão. Ele **deixa no balcão** e já volta a cozinhar o próximo.

**O truque:** o **balcão é uma fila** 🍽️🍽️🍽️. O Provador pega os pratos na ordem,
no ritmo dele. Se o Provador demorar um pouquinho num prato, os próximos **ficam
esperando no balcão** em vez de cair no chão.

> E se o balcão lotar? O restaurante é tempo-real: melhor **descartar o prato mais
> novo** do que deixar a fila crescer infinita e o alarme chegar atrasado. Prato
> velho não serve pra emergência.

Nome técnico: **`featQueue`** (uma *fila*/*queue*, com espaço pra 4 pratos).

### 📌 Bônus — O recado na parede (o Gerente não fica preso)

Quando o Provador decide "é socorro!", ele **não** larga tudo pra ir tocar o alarme.
Ele só **cola um recado na parede**: *"alarme ligado até tal hora"*. O Gerente lê o
recado e cuida do resto (piscar LED, buzzer, ligação). Assim o Provador **volta na
hora a provar o próximo prato** — a fila não para.

---

## 😱 O dia em que a cozinha pegou fogo (o bug que resolvemos)

No começo, o **Provador era workaholic**: ficava provando sem parar e **não deixava
ninguém mais usar a bancada dele**. O gerente-geral do prédio (o *watchdog*) achou
que a cozinha tinha travado e **reiniciou o restaurante inteiro**. 🔥

A solução foi ensinar boas maneiras ao Provador: depois de cada prato, ele **respira
e dá um passo pra trás por 5 milissegundos** (`vTaskDelay`), deixando os outros
usarem a bancada. Cozinha civilizada, sem reinício. ✅

*(Nome técnico do problema: **starvation** — uma tarefa "faminta" que come toda a
CPU e mata as outras de fome.)*

---

## 👅 Como o Provador aprendeu a reconhecer "socorro" (o modelo, sem susto)

O Provador não nasceu sabendo. A gente **treinou o paladar dele** com muitos exemplos:

- 🗣️ **Centenas de "socorro"** — meus e de amigos, gritado, normal e sussurrado.
- 🙅 Uma **montanha de "não é socorro"**: silêncio, ruído, conversa e — o mais
  importante — **palavras parecidas** ("corro", "socorrista", "controle"), pra ele
  não sair confundindo.

Duas lições que fizeram diferença:

1. **"Alto" não é "socorro".** No início ele achava que qualquer grito era pedido
   de ajuda. Adicionamos gente **falando alto sem gritar socorro** nos exemplos
   negativos, e ele aprendeu a prestar atenção na **palavra**, não no **volume**.
2. **Voz grave, aguda, tanto faz.** Distorcemos os áudios pra grave e agudo (nos
   dois lados), então ele aprende o **"gosto" da palavra**, não o timbre de quem fala.

E como ele decide? Ele não grita "SOCORRO!" no primeiro sinal. Ele espera a palavra
aparecer em **3 provadas seguidas** (uns 375 ms) — assim um barulho solto não engana.

### 🎤 O plot twist: o Provador não conhecia o microfone da casa

Grande susto do projeto: no computador o Provador era **impecável**, mas no ESP32
**não reconhecia nada**. Por quê? Ele tinha treinado o paladar com comida de
**outros fogões** (microfones de celular/PC) e **nunca tinha provado a comida feita
no fogão da casa** (o microfone INMP441, que tem um "tempero" próprio).

A solução foi linda de simples: **gravamos "socorro" pelo próprio microfone do
projeto** e demos essas amostras pro Provador treinar de novo. Resultado:

- 🎯 Nas 7 gravações feitas pelo microfone da casa: acerto **99% a 100%**
  (antes, várias davam **2%** — ele nem percebia).
- ✅ Sem estragar o que já sabia (**95%** dos acertos antigos mantidos).
- 🚫 **Zero alarme falso** nos negativos.

> A moral pra contar na banca: **em edge ML, o modelo tem que treinar com o sensor
> de verdade.** Foi isso que fez o restaurante finalmente funcionar no chip.

---

## 🧾 Resumindo em uma linha cada

- **👂 Ouvinte (T1):** anota o som sem parar → prioridade máxima.
- **🔪 Cozinheiro (T2):** som vira prato padrão (MFCC) → bancada só pra ele.
- **👅 Provador (T3):** o prato é socorro? (rede neural) → decide com calma.
- **🚨 Gerente (T4):** é socorro! → LED, buzzer e liga pra emergência.
- **🖊️ Mutex:** caneta única no caderno compartilhado.
- **🔔 Semáforo:** campainha "tá pronto".
- **🍽️ Fila:** balcão de pratos entre cozinheiro e provador.

E o mais bonito: **nada de áudio sai do restaurante**. Só o *alarme* vai pra rua —
o som fica na cozinha. Mais privacidade, menos internet. 🆘
