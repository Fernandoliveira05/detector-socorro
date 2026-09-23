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
  if (WiFi.status() == WL_CONNECTED) {
    // Hotspot de celular costuma entregar um DNS interno que o ESP não resolve.
    // Mantém o IP/gateway do DHCP, mas força DNS público (Google/Cloudflare).
    WiFi.config(WiFi.localIP(), WiFi.gatewayIP(), WiFi.subnetMask(),
                IPAddress(8,8,8,8), IPAddress(1,1,1,1));
    Serial.printf(" ok  IP=%s  DNS=8.8.8.8\n", WiFi.localIP().toString().c_str());
  } else {
    Serial.println(" FALHOU (segue offline)");
  }
}

// POST autenticado na API do Twilio (Calls.json ou Messages.json).
static void twilioPost(const String& endpoint, const String& body) {
  if (WiFi.status() != WL_CONNECTED) { Serial.println("[Twilio] sem WiFi"); return; }
  Serial.printf("[Twilio] heap livre=%u  maior bloco=%u\n",
                ESP.getFreeHeap(), ESP.getMaxAllocHeap());
  // DIAGNÓSTICO: separa DNS de alcance TCP
  IPAddress ip;
  bool dns = WiFi.hostByName("api.twilio.com", ip);
  Serial.printf("[Twilio] DNS api.twilio.com -> %s\n", dns ? ip.toString().c_str() : "FALHOU");
  WiFiClientSecure client;
  client.setInsecure();                 // demo: pula validação de cert
  client.setBufferSizes(8192, 2048);    // reduz buffers TLS: sobra heap contíguo p/ o parse do cert (X509)
  client.setHandshakeTimeout(30);       // s: dá tempo pro TLS da Twilio
  HTTPClient http;
  http.setConnectTimeout(20000);        // ms: TCP+TLS connect
  http.setTimeout(20000);               // ms: resposta
  http.begin(client, "https://api.twilio.com/2010-04-01/Accounts/" + String(TWILIO_SID) + endpoint);
  http.setAuthorization(TWILIO_SID, TWILIO_TOKEN);   // login = SID, senha = token
  http.addHeader("Content-Type", "application/x-www-form-urlencoded");
  int code = http.POST(body);
  Serial.printf("[Twilio] %s -> HTTP %d (%s)\n",
                endpoint.c_str(), code, http.errorToString(code).c_str());
  if (code > 0) { String r = http.getString(); Serial.printf("[Twilio] resp: %s\n", r.substring(0, 200).c_str()); }
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
