// ============================================================================
// secrets.h — credenciais (NÃO versionar!). Copie este arquivo para "secrets.h"
// e preencha. Adicione "secrets.h" ao .gitignore.
// ============================================================================
#pragma once

// --- WiFi ---
#define WIFI_SSID   "SUA_REDE_WIFI"
#define WIFI_PASS   "SUA_SENHA"

// --- Twilio (https://console.twilio.com) ---
#define TWILIO_SID    "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"   // Account SID
#define TWILIO_TOKEN  "seu_auth_token_aqui"                  // Auth Token
#define TWILIO_FROM   "+15005550006"    // número Twilio (comprado/trial)
#define ALERT_TO      "+55DDDNUMERO"    // número que recebe a ligação/SMS (o "190" simulado)

// TwiML: URL que o Twilio busca ao atender a ligação (o que a "polícia" ouve).
// Crie um TwiML Bin no console Twilio com algo como:
//   <Response><Say language="pt-BR" voice="Polly.Camila">
//     Emergência. Pedido de socorro detectado. Enviando ajuda.
//   </Say></Response>
#define TWIML_URL   "https://handler.twilio.com/twiml/EHxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

// Escolha: fazer LIGAÇÃO (true) ou só SMS (false)
#define USE_CALL    true
// Mensagem do SMS (se USE_CALL=false, ou como complemento)
#define ALERT_SMS_BODY  "ALERTA: pedido de SOCORRO detectado pelo sensor acustico."
