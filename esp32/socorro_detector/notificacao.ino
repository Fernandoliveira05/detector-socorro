// ============================================================================
//  notificacao.ino — WiFi + ligação/SMS via Twilio (Fase 2)
//  (arquivo separado para o programa principal ficar simples de ler)
// ============================================================================
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include "secrets.h"          // copie secrets_exemplo.h -> secrets.h e preencha

// Conecta no WiFi (para a ligação Twilio). Se falhar, segue offline.
void wifiSetup() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("Conectando WiFi");
  for (int i = 0; i < 40 && WiFi.status() != WL_CONNECTED; i++) { delay(250); Serial.print("."); }
  Serial.println(WiFi.status() == WL_CONNECTED ? " ok" : " FALHOU (segue offline)");
}

// POST autenticado na API do Twilio (Calls.json ou Messages.json).
static void twilioPost(const String& endpoint, const String& body) {
  if (WiFi.status() != WL_CONNECTED) { Serial.println("[Twilio] sem WiFi"); return; }
  Serial.printf("[Twilio] heap livre=%u  maior bloco=%u\n",
                ESP.getFreeHeap(), ESP.getMaxAllocHeap());
  WiFiClientSecure client; client.setInsecure();     // demo: pula validação de cert
  HTTPClient http;
  http.begin(client, "https://api.twilio.com/2010-04-01/Accounts/" + String(TWILIO_SID) + endpoint);
  http.setAuthorization(TWILIO_SID, TWILIO_TOKEN);   // login = SID, senha = token
  http.addHeader("Content-Type", "application/x-www-form-urlencoded");
  int code = http.POST(body);
  Serial.printf("[Twilio] %s -> HTTP %d\n", endpoint.c_str(), code);
  http.end();
}

// codifica texto p/ URL (espaços, acentos, etc.)
static String enc(const String& s) {
  String o; char b[4];
  for (char c : s) {
    if (isalnum(c) || c=='-'||c=='_'||c=='.'||c=='~') o += c;
    else { sprintf(b, "%%%02X", (unsigned char)c); o += b; }
  }
  return o;
}

// Faz a LIGAÇÃO (ou SMS) simulando o chamado à polícia.
void ligarParaPolicia(float p) {
  Serial.println("[Twilio] SIMULANDO LIGACAO PARA A POLICIA (190)...");
  if (USE_CALL)
    twilioPost("/Calls.json",
               "To=" + enc(ALERT_TO) + "&From=" + enc(TWILIO_FROM) + "&Url=" + enc(TWIML_URL));
  else
    twilioPost("/Messages.json",
               "To=" + enc(ALERT_TO) + "&From=" + enc(TWILIO_FROM) +
               "&Body=" + enc(String(ALERT_SMS_BODY)));
}
