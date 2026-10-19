#include <Arduino.h>
#include <ArduinoJson.h>
#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>
#include <freertos/task.h>
#include <HTTPClient.h>
#include <LittleFS.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <math.h>
#include <string.h>
#include <time.h>

#include "device_config.h"

#ifndef NEXUS_FORMAT_FILESYSTEM_ONCE
#define NEXUS_FORMAT_FILESYSTEM_ONCE 0
#endif

namespace {
constexpr char kQueuePath[] = "/events.json";
constexpr char kFirmwareVersion[] = NEXUS_FIRMWARE_VERSION;
constexpr uint8_t kMaxQueuedEvents = 32;
constexpr uint32_t kHeartbeatIntervalMs = 60'000;
constexpr uint32_t kRetryIntervalMs = 5'000;
constexpr uint32_t kNtpRetryIntervalMs = 20'000;
constexpr uint32_t kButtonDebounceMs = 50;
constexpr uint32_t kHttpTimeoutMs = 12'000;
constexpr char kNtpServer[] = "pool.ntp.org";
constexpr char kTimeZone[] = "UTC0";

uint32_t lastHeartbeat = 0;
uint32_t lastRetry = 0;
uint32_t lastNtpAttempt = 0;
uint32_t lastButtonChange = 0;
bool stableButtonState = HIGH;
bool sampledButtonState = HIGH;
volatile bool sosPending = false;
volatile bool sosAcceptedByApi = false;
SemaphoreHandle_t queueMutex = nullptr;

bool configIsUsable() {
  return strlen(NEXUS_WIFI_SSID) > 0 && strlen(NEXUS_WIFI_PASSWORD) > 0 &&
         strlen(NEXUS_DEVICE_ID) > 0 && strlen(NEXUS_DEVICE_SECRET) > 0 &&
         strncmp(NEXUS_API_BASE, "https://", 8) == 0 &&
         NEXUS_API_ROOT_CA_CONFIGURED == 1;
}

String newEventId() {
  char id[37];
  uint8_t bytes[16];
  for (uint8_t i = 0; i < sizeof(bytes); ++i) bytes[i] = static_cast<uint8_t>(esp_random());
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  snprintf(id, sizeof(id), "%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-%02x%02x%02x%02x%02x%02x",
           bytes[0], bytes[1], bytes[2], bytes[3], bytes[4], bytes[5], bytes[6], bytes[7],
           bytes[8], bytes[9], bytes[10], bytes[11], bytes[12], bytes[13], bytes[14], bytes[15]);
  return String(id);
}

bool readQueue(JsonDocument &queue) {
  queue.clear();
  if (!LittleFS.exists(kQueuePath)) {
    queue.to<JsonArray>();
    return true;
  }
  File file = LittleFS.open(kQueuePath, "r");
  if (!file) return false;
  const DeserializationError error = deserializeJson(queue, file);
  file.close();
  return !error && queue.is<JsonArray>();
}

bool writeQueue(JsonDocument &queue) {
  File file = LittleFS.open("/events.tmp", "w");
  if (!file) return false;
  const size_t written = serializeJson(queue, file);
  file.flush();
  file.close();
  if (written == 0 || !LittleFS.rename("/events.tmp", kQueuePath)) {
    LittleFS.remove("/events.tmp");
    return false;
  }
  return true;
}

bool enqueueEvent(const char *path, JsonDocument &payload, bool isSos = false) {
  if (queueMutex == nullptr || xSemaphoreTake(queueMutex, portMAX_DELAY) != pdTRUE) return false;
  JsonDocument queue;
  if (!readQueue(queue)) {
    Serial.println("ERROR: durable event queue is unreadable; refusing to send an unpersisted event.");
    xSemaphoreGive(queueMutex);
    return false;
  }
  JsonArray events = queue.as<JsonArray>();
  if (events.size() >= kMaxQueuedEvents) {
    Serial.println(isSos ? "ERROR: queue full; manual SOS could not be persisted." : "Event queue full; event not accepted.");
    xSemaphoreGive(queueMutex);
    return false;
  }

  JsonObject item = events.add<JsonObject>();
  item["path"] = path;
  item["payload"] = payload.as<JsonVariantConst>();
  if (!writeQueue(queue)) {
    Serial.println("ERROR: event could not be persisted; it will not be transmitted.");
    xSemaphoreGive(queueMutex);
    return false;
  }
  xSemaphoreGive(queueMutex);
  return true;
}

bool networkTimeReady() {
  return time(nullptr) > 1'700'000'000;
}

int postEvent(const char *path, JsonVariantConst payload) {
  if (WiFi.status() != WL_CONNECTED || !networkTimeReady()) return -1;
  WiFiClientSecure tls;
  tls.setCACert(NEXUS_API_ROOT_CA);
  HTTPClient http;
  const String url = String(NEXUS_API_BASE) + "/" + path;
  if (!http.begin(tls, url)) return -1;
  http.setTimeout(kHttpTimeoutMs);
  http.addHeader("Authorization", String("Device ") + NEXUS_DEVICE_ID + ":" + NEXUS_DEVICE_SECRET);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("Accept", "application/json");
  String body;
  serializeJson(payload, body);
  const int status = http.POST(body);
  if (status < 0) Serial.printf("Network error posting %s: %s\n", path, http.errorToString(status).c_str());
  else Serial.printf("POST %s -> HTTP %d\n", path, status);
  http.end();
  return status;
}

void flushQueue() {
  if (WiFi.status() != WL_CONNECTED || !networkTimeReady()) return;
  if (xSemaphoreTake(queueMutex, portMAX_DELAY) != pdTRUE) return;
  JsonDocument queue;
  if (!readQueue(queue)) {
    Serial.println("ERROR: durable event queue is unreadable.");
    xSemaphoreGive(queueMutex);
    return;
  }
  JsonArray events = queue.as<JsonArray>();
  if (events.isNull() || events.size() == 0) {
    xSemaphoreGive(queueMutex);
    return;
  }
  JsonDocument pending;
  if (pending.set(events[0]) == false) {
    Serial.println("ERROR: queued event could not be copied; retained for inspection.");
    xSemaphoreGive(queueMutex);
    return;
  }
  xSemaphoreGive(queueMutex);

  const char *path = pending["path"] | "";
  JsonVariantConst payload = pending["payload"].as<JsonVariantConst>();
  if (path[0] == '\0' || payload.isNull()) {
    Serial.println("ERROR: malformed queued event retained for inspection.");
    return;
  }
  const String expectedEventId = pending["payload"]["event_id"] | "";
  const int status = postEvent(path, payload);
  if (status < 200 || status >= 300) return;
  if (strcmp(path, "incidents/sos/") == 0) {
    sosPending = false;
    sosAcceptedByApi = true;
  }

  // Remove only the event that was sent. The SOS loop may have appended new
  // records while this task waited on HTTP, so queue changes are mutex-guarded.
  if (xSemaphoreTake(queueMutex, portMAX_DELAY) != pdTRUE) return;
  JsonDocument latest;
  if (readQueue(latest)) {
    JsonArray currentEvents = latest.as<JsonArray>();
    if (!currentEvents.isNull() && currentEvents.size() > 0) {
      const String currentEventId = currentEvents[0]["payload"]["event_id"] | "";
      if (currentEventId == expectedEventId) {
        currentEvents.remove(0);
        if (!writeQueue(latest)) Serial.println("ERROR: queue acknowledgement could not be persisted.");
      }
    }
  }
  xSemaphoreGive(queueMutex);
}

void beginNetworkTimeSync() {
  configTzTime(kTimeZone, kNtpServer);
}

void sendHeartbeat() {
  if (WiFi.status() != WL_CONNECTED || !networkTimeReady()) return;
  JsonDocument payload;
  payload["firmware_version"] = kFirmwareVersion;
  // Battery reporting is omitted until a board-specific, calibrated battery
  // adapter is configured; do not report a fabricated percentage.
  postEvent("devices/heartbeat/", payload.as<JsonVariantConst>());
}

void networkWorker(void *) {
  for (;;) {
    const uint32_t now = millis();
    if (WiFi.status() == WL_CONNECTED && !networkTimeReady() && now - lastNtpAttempt >= kNtpRetryIntervalMs) {
      lastNtpAttempt = now;
      beginNetworkTimeSync();
    }
    if (WiFi.status() == WL_CONNECTED && now - lastRetry >= kRetryIntervalMs) {
      lastRetry = now;
      flushQueue();
    }
    if (now - lastHeartbeat >= kHeartbeatIntervalMs) {
      lastHeartbeat = now;
      sendHeartbeat();
    }
    vTaskDelay(pdMS_TO_TICKS(250));
  }
}

void captureManualSos() {
  JsonDocument payload;
  payload["event_id"] = newEventId();
  payload["trigger_source"] = "wearable";
  if (enqueueEvent("incidents/sos/", payload, true)) {
    sosPending = true;
    sosAcceptedByApi = false;
    Serial.println("Manual SOS persisted. Delivery/incident creation is not confirmed until HTTP success.");
  }
}

void pollSosButton() {
  const bool sample = digitalRead(NEXUS_SOS_BUTTON_PIN);
  if (sample != sampledButtonState) {
    sampledButtonState = sample;
    lastButtonChange = millis();
  }
  if (millis() - lastButtonChange < kButtonDebounceMs || sample == stableButtonState) return;
  stableButtonState = sample;
  if (stableButtonState == LOW) captureManualSos();
}
}  // namespace

void setup() {
  Serial.begin(115200);
  pinMode(NEXUS_SOS_BUTTON_PIN, INPUT_PULLUP);
  pinMode(NEXUS_STATUS_LED_PIN, OUTPUT);
  digitalWrite(NEXUS_STATUS_LED_PIN, LOW);

  if (!configIsUsable()) {
    Serial.println("ERROR: configure include/device_config.h with Wi-Fi, issued device credentials, HTTPS API and trusted root CA.");
    while (true) { digitalWrite(NEXUS_STATUS_LED_PIN, !digitalRead(NEXUS_STATUS_LED_PIN)); delay(250); }
  }
  if (!LittleFS.begin(NEXUS_FORMAT_FILESYSTEM_ONCE != 0)) {
    Serial.println("ERROR: LittleFS mount failed; refusing to format storage that may contain queued SOS events.");
    while (true) delay(1000);
  }
  if (NEXUS_FORMAT_FILESYSTEM_ONCE != 0) {
    Serial.println("WARNING: one-time filesystem format enabled; remove NEXUS_FORMAT_FILESYSTEM_ONCE and rebuild now.");
  }
  queueMutex = xSemaphoreCreateMutex();
  if (queueMutex == nullptr) {
    Serial.println("ERROR: event queue mutex allocation failed.");
    while (true) delay(1000);
  }
  JsonDocument bootQueue;
  if (!readQueue(bootQueue)) {
    Serial.println("ERROR: existing event queue cannot be read; refusing to overwrite it.");
    while (true) delay(1000);
  }
  for (JsonVariantConst event : bootQueue.as<JsonArrayConst>()) {
    if (event["path"] == "incidents/sos/") {
      sosPending = true;
      break;
    }
  }

  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(NEXUS_WIFI_SSID, NEXUS_WIFI_PASSWORD);
  Serial.println("Starting Wi-Fi in background; manual SOS remains responsive while offline.");
  xTaskCreatePinnedToCore(networkWorker, "nexus-network", 8192, nullptr, 1, nullptr, 0);
}

void loop() {
  pollSosButton();
  static uint32_t lastStatusToggle = 0;
  static bool pendingLedOn = false;
  if (sosAcceptedByApi) {
    digitalWrite(NEXUS_STATUS_LED_PIN, HIGH);
  } else if (sosPending && millis() - lastStatusToggle >= 250) {
    lastStatusToggle = millis();
    pendingLedOn = !pendingLedOn;
    digitalWrite(NEXUS_STATUS_LED_PIN, pendingLedOn ? HIGH : LOW);
  } else if (!sosPending) {
    digitalWrite(NEXUS_STATUS_LED_PIN, LOW);
  }
  // Sensor adapters must call publishMeasurement with an explicitly validated
  // sensor value. No sample measurement or fall classification is fabricated.
  delay(10);
}

// Sensor-driver integration point. Call only with a real reading from an
// attached, configured sensor adapter; backend assigns patient/device/source.
bool publishMeasurement(const char *measurementType, float value, const char *unit, const char *measuredAtUtc) {
  if (!measurementType || !unit || !measuredAtUtc || !isfinite(value) || value < 0) return false;
  JsonDocument payload;
  payload["event_id"] = newEventId();
  payload["measurement_type"] = measurementType;
  payload["value"] = value;
  payload["unit"] = unit;
  payload["measured_at"] = measuredAtUtc;
  const String path = "measurements/";
  return enqueueEvent(path.c_str(), payload);
}
