<div align="center">

# 🆘 SOS-ESP — um detector de "socorro" que cabe na palma da mão

**Detector de Anomalias Acústicas · Ponderada · Sistemas Embarcados + Edge ML**

<sub>Um ESP32 que fica de ouvido em pé, reconhece a palavra "socorro" e chama ajuda — sem mandar áudio nenhum pra nuvem.</sub>

</div>

---

## A ideia, em poucas linhas

Todo pedido de socorro tem uma coisa em comum: alguém grita "socorro". Parece
óbvio, mas ensinar um chip minúsculo a **entender essa palavra em tempo real** —
e só ela — é um problema bem gostoso de resolver.

A escolha do som (o enunciado deixou livre) foi **"socorro"**, porque encaixa no
caso "grito/alarme em ambiente monitorado" e tem um uso prático real: um sensor
barato que, ao ouvir um pedido de ajuda, **acende um alerta e liga para a
emergência** — pense em monitoramento de idosos, segurança pessoal ou ambientes
de risco.

O pulo do gato é que **tudo acontece na borda**: o áudio vira números (MFCC)
dentro do próprio ESP32, uma rede neural decide se foi "socorro", e só o **evento**
(o alerta) sai do dispositivo — nunca o áudio bruto. Menos banda, mais privacidade.

## Como funciona (em 3 tempos)

```
🎙  Ouvir  ──►  🔢 Resumir  ──►  🧠 Decidir  ──►  🚨 Alertar
 microfone      MFCC (49×16)     CNN (TFLite)      LED + ligação
```

1. **Ouvir** — o microfone I2S enche um buffer circular com o último 1 segundo.
2. **Resumir** — esse trecho vira uma "impressão digital" sonora (MFCC).
3. **Decidir** — uma CNN pequena dá a probabilidade de ser "socorro".
4. **Alertar** — se a detecção se sustenta, acende o **LED vermelho** e dispara
   uma **ligação de emergência** (via Twilio).

E isso roda tudo **ao mesmo tempo**, com o **FreeRTOS** coordenando 4 tarefas em
paralelo (captura, features, detecção, alerta) — o coração da ponderada.

## O que tem aqui

| Pasta | O que é |
|---|---|
| `firmware/` | O código C++ que roda no ESP32: as 4 tarefas do RTOS, captura I2S, features e o modelo embarcado. |
| `treino/` | Como o modelo nasceu: preparo dos dados, treino da CNN, exportação e um demo pra rodar no PC. |
| `docs/` | Relatório técnico e o diagrama das tarefas RTOS. |

## Como o modelo aprendeu

Gravei **centenas de "socorro"** — meus e de amigos — em vários tons (grito, normal,
sussurro) e ambientes. Pra ele não sair disparando em qualquer barulho, juntei uma
montanha de **negativos**: ruído, silêncio, conversa, e principalmente **palavras
parecidas** ("corro", "controle", "socorrista"). Duas sacadas fizeram diferença:

- **Normalização global fixa** das features → probabilidades estáveis (nada de
  "0 a 0.9" à toa).
- **Variações de voz simétricas** (grave/aguda) aplicadas a positivos *e*
  negativos → o modelo aprende a **palavra**, não o tom nem o volume.

Resultado medido com validação cruzada: **AUC ≈ 0.98**, e detecção consistente nos
três tons de voz.

## Rodando

**No PC (demo da detecção):**
```bash
cd treino
python demo_mic.py          # grite "socorro" e veja a barra subir
```

**Código de teste (simula anomalias e mede performance):**
```bash
cd treino
python testar.py            # mede a latência de inferência (sem áudio)
python testar.py ../audios  # + acurácia: roda o modelo em socorro vs não-socorro
```
Ele reporta **latência** (ms por inferência) e, apontando para a pasta de áudios
(subpastas `socorro/` e `nao_socorro/`), a **precisão, recall e acurácia**.

**No ESP32 (firmware):** abra `firmware/socorro_detector/socorro_detector.ino` no
Arduino IDE (placa *ESP32 Dev Module* + biblioteca *TensorFlow Lite Micro*), copie
`secrets_exemplo.h` → `secrets.h`, e envie. As ligações da protoboard estão em
[`docs/ligacoes-protoboard.md`](docs/ligacoes-protoboard.md) e a ligação de
emergência em [`docs/twilio.md`](docs/twilio.md).

## Checklist do enunciado

| Pedido | Onde está |
|---|---|
| Captura via ESP32 + INMP441 | `firmware/` · tarefa de Captura (I2S) |
| Detecção com modelo pré-treinado | `firmware/` · TFLite Micro + `treino/` |
| RTOS com ≥ 3 tarefas sincronizadas | **4 tarefas** + mutex, semáforo e fila |
| Latência de cada etapa medida | logs no Serial + `docs/relatorio_tecnico.md` |
| Alerta por LED/buzzer | tarefa de Alerta (LED vermelho + buzzer) |
| Conflitos de concorrência resolvidos | mutex (buffer) + fila (features→detecção) |
| Modelo `.onnx` | `treino/modelos/socorro.onnx` |
| Diagrama de tarefas RTOS | `docs/diagrama_rtos.svg` |
| Relatório técnico | `docs/relatorio_tecnico.md` |
| Código de teste (simula + mede performance) | `treino/testar.py` |

## Links

- 🎥 **Vídeo da demonstração:** _(colar link aqui)_
- 📁 **Áudios do dataset (Drive):** _(colar link aqui)_

---

<div align="center">
<sub>Feito com café, muitos "SOCORRO!" gritados no microfone, e um ESP32 corajoso. 🆘</sub>
</div>
