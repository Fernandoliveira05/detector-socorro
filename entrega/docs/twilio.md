# Fase 2 — Ligação real pra "polícia" via Twilio

O ESP32 (com WiFi) chama a API do Twilio e faz uma **ligação telefônica real**
(ou SMS) quando detecta socorro. Dispara **1 vez por evento** (cooldown de 30 s).

## 1. Criar conta e pegar credenciais
1. Crie conta em https://www.twilio.com/try-twilio (trial grátis dá crédito).
2. No Console, copie **Account SID** e **Auth Token**.
3. Pegue um **número Twilio** (trial dá um número de teste). Esse é o `TWILIO_FROM`.
4. No trial, só dá pra ligar/mandar SMS para **números verificados** — verifique
   o seu celular em *Verified Caller IDs* e use-o como `ALERT_TO` (o "190" simulado).

## 2. Criar o TwiML (o que a "polícia" ouve ao atender)
1. Console → *Develop → TwiML Bins → Create*.
2. Conteúdo:
   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <Response>
     <Say language="pt-BR" voice="Polly.Camila">
       Emergência. Um pedido de socorro foi detectado pelo sensor acústico.
       Enviando ajuda ao local.
     </Say>
   </Response>
   ```
3. Copie a URL do TwiML Bin → é o `TWIML_URL`.

## 3. Preencher as credenciais
```bash
cd projeto/firmware/socorro_detector
cp secrets_exemplo.h secrets.h
# edite secrets.h com WIFI_SSID/PASS, TWILIO_SID/TOKEN/FROM, ALERT_TO, TWIML_URL
```
`secrets.h` já está no `.gitignore` (não vai pro repositório).

## 4. Bibliotecas (Arduino IDE)
- WiFi, WiFiClientSecure, HTTPClient — já vêm com o core **Arduino-ESP32**.
- (a validação de certificado usa `setInsecure()` p/ simplificar a demo).

## 5. Testar
1. Envie o firmware. Monitor Serial (115200): deve mostrar `Conectando WiFi ok`.
2. Grite "SOCORRO". Esperado:
   - LED vermelho pisca ~8 s, buzzer bipa;
   - Serial: `[Twilio] SIMULANDO LIGACAO PARA A POLICIA (190)...` e `HTTP 201`;
   - seu celular (`ALERT_TO`) **toca** e reproduz a mensagem do TwiML.

## Alternar ligação ↔ SMS
Em `secrets.h`: `#define USE_CALL true` (ligação) ou `false` (SMS com `ALERT_SMS_BODY`).

> **Nota de segurança/ética**: use um número SEU como destino. Não ligue para o 190
> real — isto é uma **simulação** de fluxo de emergência para fins didáticos.
