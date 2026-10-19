# ESP32 device client (hardware integration scaffold)

This PlatformIO/Arduino firmware implements the Nexus Sync device HTTP transport and a debounced, independent manual SOS input. It is a configurable integration scaffold, not validated firmware for a particular wearable, sensor, battery, or enclosure.

## What it does

- Connects to Wi-Fi and synchronizes time in the background before making HTTPS requests; manual SOS capture stays responsive while time/network are unavailable.
- Uses the backend's `Authorization: Device <identifier>:<secret>` scheme and a configured trusted root CA. TLS certificate verification is mandatory; there is no insecure TLS fallback.
- Sends periodic device heartbeats with the firmware version.
- Persists event payloads and their UUID idempotency keys in LittleFS before transmission; retains failed events for retry after connectivity/auth recovery.
- Debounces a physical button and records `trigger_source: wearable` SOS events locally before transmission. The backend derives patient/device identity from the credential. Button activation is not represented as server acknowledgement or dispatch.
- Blinks the configured status LED while SOS is queued and holds it on after the API returns success; neither state represents provider acknowledgement or dispatch.
- Runs blocking HTTPS work in a background FreeRTOS task so button polling is not delayed by request timeouts.
- Exposes `publishMeasurement(...)` as an adapter point for a separately selected and validated sensor driver. It does not invent measurements, classify falls, or estimate body temperature/BP.

## Build setup

1. Install PlatformIO Core or the VS Code PlatformIO extension.
2. Copy `include/device_config.example.h` to `include/device_config.h` and fill in Wi-Fi details, the device identifier and one-time issued device secret, API base URL, and the deployment's trusted root CA PEM. Set `NEXUS_API_ROOT_CA_CONFIGURED` to `1` only after replacing the certificate placeholder. `device_config.h` is intentionally ignored by Git.
3. In PlatformIO, build/upload the `nexus-wearable` environment and open the serial monitor at 115200 baud.
4. Check the ESP32 board's pinout and connect the SOS switch between GPIO 4 (configurable) and ground. Verify the LED wiring or configure its pin before powering the device.
5. Activate/assign the wearable and issue its credential through the operations workflow before expecting ingestion to succeed. Revoke and reissue credentials if the secret is lost; it cannot be recovered from the backend.

Do not put real secrets in source control or screenshots. Use HTTPS and replace the CA placeholder; the firmware refuses to start unless the configuration flag is explicitly enabled. Protect physical/debug access and provision each device individually.

On a new board only, the LittleFS partition must be initialized once. Temporarily add `-DNEXUS_FORMAT_FILESYSTEM_ONCE=1` to the environment's `build_flags`, build and flash, then remove the flag and rebuild/flash immediately. Formatting erases queued events, so never enable this option on a device that may hold user data. Normal firmware mounts without formatting and stops rather than erase an unreadable queue; pending SOS records are restored to the status indicator after reboot.

## Hardware-specific work still required

- Confirm the exact ESP32 board, button circuit, enclosure, battery, charging and low-power behavior.
- Implement sensor adapter drivers only for selected hardware, quality flags, sampling/calibration, and timestamp acquisition; validate against appropriate references. Do not report MAX30102 as BP or skin temperature as body temperature.
- Implement board-specific calibrated battery telemetry before sending a battery percentage. This firmware deliberately omits that field rather than making an inaccurate estimate.
- Test flash queue recovery, power-loss behavior, Wi-Fi loss, credential revocation, duplicate replay, SOS latency, TLS/time failure, and brownout behavior on the target board.
- Define secure boot, flash encryption, signed OTA/update and key rotation procedures before field deployment. This scaffold does not provide secure OTA or physical tamper resistance.

`publishMeasurement()` expects the backend's measurement type, units, and an ISO-8601 UTC timestamp. It queues the value unchanged; sensor validation and clinical review remain external gates.
