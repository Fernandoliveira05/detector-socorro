# Ligação na protoboard — ESP32 + INMP441 + LED vermelho

## Componentes
- ESP32 DevKit
- Microfone I2S INMP441
- 1 LED vermelho + resistor 220–330 Ω
- (opcional) buzzer passivo
- Jumpers + protoboard

## Conexões

### INMP441 (microfone I2S)
| INMP441 | ESP32 | Cor sugerida |
|---------|-------|--------------|
| VDD | 3V3 | vermelho |
| GND | GND | preto |
| L/R | GND | (seleciona canal esquerdo) |
| WS  | GPIO25 | amarelo |
| SCK | GPIO26 | azul |
| SD  | GPIO33 | verde |

### LED vermelho (alerta de socorro)
```
GPIO23 ──►|── [220Ω] ── GND
        LED(+)  resistor
```
| LED | ESP32 |
|-----|-------|
| ânodo (+, perna longa) → resistor → | GPIO23 |
| cátodo (−, perna curta) | GND |

### Buzzer (opcional)
| Buzzer | ESP32 |
|--------|-------|
| + | GPIO27 |
| − | GND |

## Esquema (topo da protoboard)

```
            ESP32 DevKit
          ┌───────────────┐
   3V3 ───┤3V3         GND ├─── GND (trilho azul)
          │               │
  GPIO25 ─┤25 (WS)    (SD) ├─ GPIO33 ──── INMP441.SD
  GPIO26 ─┤26 (SCK)        │
          │           23   ├─ GPIO23 ──[220Ω]──►|── GND   (LED vermelho)
          │           27   ├─ GPIO27 ─────────── buzzer + │
          └───────────────┘
   INMP441:  VDD→3V3  GND→GND  L/R→GND  WS→25  SCK→26  SD→33
```

## Como testar (Fase 1)
1. Ligue tudo, envie o firmware (`socorro_detector.ino`).
2. Abra o Monitor Serial (115200).
3. Grite "SOCORRO" perto do microfone.
4. Esperado: **LED vermelho pisca por ~8 s**, o buzzer bipa, e o Serial fica
   "postando": `[ALERTA] SOCORRO detectado (p=…) — LED vermelho ligado, postando...`

Pinos configuráveis em [`socorro_detector/config.h`](socorro_detector/config.h)
(`PIN_LED_RED`, `ALERT_HOLD_MS`, `BLINK_MS`, `POST_INTERVAL_MS`).
