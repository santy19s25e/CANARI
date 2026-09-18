#include <WiFi.h>
#include <HTTPClient.h>
#include <time.h>
#include <esp_system.h>

const char* WIFI_SSID = "CAMBIAR_RED";
const char* WIFI_PASSWORD = "CAMBIAR_CLAVE_WIFI";
const char* SERVER_URL = "http://192.168.1.10:8000/api/telemetry";
const char* INGEST_KEY = "COPIAR_DATA_INGEST_KEY";
const char* NODE_ID = "N03";
const unsigned long INTERVAL_MS = 3000;
unsigned long lastSend = 0;
uint32_t sessionId;
uint32_t sequenceId = 0;

void setup() {
  Serial.begin(115200);
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
  sessionId = esp_random();
}

void loop() {
  if (millis() - lastSend < INTERVAL_MS) { delay(10); return; }
  lastSend = millis();
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Sin Wi-Fi; servidor marcará muestra vencida");
    WiFi.reconnect();
    return;
  }
  time_t now = time(nullptr);
  if (now < 1704067200) { Serial.println("Esperando sincronización UTC por NTP"); return; }
  struct tm utc;
  gmtime_r(&now, &utc);
  char captured[32], sampleId[64], payload[640];
  strftime(captured, sizeof(captured), "%Y-%m-%dT%H:%M:%SZ", &utc);
  snprintf(sampleId, sizeof(sampleId), "esp32_%08lx_%lu", (unsigned long)sessionId, (unsigned long)sequenceId);
  
  float ch4 = ((sequenceId / 5) % 3 == 2) ? 1.6 : 0.2;
  snprintf(payload, sizeof(payload),
    "{\"node_id\":\"%s\",\"sample_id\":\"%s\",\"captured_at\":\"%s\","
    "\"source\":\"simulation\",\"device_status\":\"ok\",\"calibration_ref\":\"\","
    "\"values\":{\"ch4_vol_pct\":%.2f,\"o2_vol_pct\":20.9,\"temperature_c\":24.0,\"humidity_pct\":65.0}}",
    NODE_ID, sampleId, captured, ch4);
  HTTPClient http;
  http.setTimeout(5000);
  http.begin(SERVER_URL);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("Authorization", String("Bearer ") + INGEST_KEY);
  int code = http.POST((uint8_t*)payload, strlen(payload));
  Serial.printf("Envío simulado %lu, HTTP %d\n", (unsigned long)sequenceId, code);
  http.end();
  sequenceId++;
}
