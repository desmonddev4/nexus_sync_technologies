#pragma once

// Copy to device_config.h locally. Never commit device_config.h or real secrets.
#define NEXUS_WIFI_SSID "replace-me"
#define NEXUS_WIFI_PASSWORD "replace-me"
#define NEXUS_API_BASE "https://your-api.example/api/v1"
#define NEXUS_DEVICE_ID "device-identifier-issued-by-operations"
#define NEXUS_DEVICE_SECRET "one-time-secret-issued-by-operations"
#define NEXUS_FIRMWARE_VERSION "esp32-0.1.0"
#define NEXUS_API_ROOT_CA_CONFIGURED 0

// PEM root CA for the API host. TLS is intentionally fail-closed; do not use
// setInsecure(). Replace this placeholder with the deployment's trusted chain.
static const char NEXUS_API_ROOT_CA[] PROGMEM = R"CERT(
-----BEGIN CERTIFICATE-----
REPLACE_WITH_TRUSTED_ROOT_CA
-----END CERTIFICATE-----
)CERT";

// GPIO 4 is a common ESP32 development-board input; confirm the selected board's
// pinout and wire the physical SOS switch between this pin and ground.
constexpr int NEXUS_SOS_BUTTON_PIN = 4;
constexpr int NEXUS_STATUS_LED_PIN = 2;
