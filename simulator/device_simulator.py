"""Small authenticated device simulator for the Nexus Sync API.

Credentials are read only from environment variables and are never written to disk.
Queued event payloads contain test health/location data; keep the queue file private.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
QUEUE_PATH = ROOT / ".device-event-queue.jsonl"


def api_request(api_base: str, device_id: str, secret: str, path: str, payload: dict) -> dict:
    url = f"{api_base.rstrip('/')}/{path.lstrip('/')}"
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Device {device_id}:{secret}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API returned HTTP {error.code}: {detail}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"API connection failed: {error.reason}") from error


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def event_payloads(args: argparse.Namespace) -> list[tuple[str, str, dict]]:
    now = utc_now()
    data: list[tuple[str, str, dict]] = []
    if args.event in ("heartbeat", "all"):
        data.append(("heartbeat", "devices/heartbeat/", {
            "battery_percent": args.battery,
            "firmware_version": args.firmware,
        }))
    if args.event in ("measurement", "all"):
        data.append(("measurement", "measurements/", {
            "event_id": str(uuid.uuid4()),
            "measurement_type": args.measurement_type,
            "value": args.value,
            "unit": args.unit,
            "measured_at": now,
        }))
    if args.event in ("location", "all"):
        data.append(("location", "locations/", {
            "event_id": str(uuid.uuid4()),
            "latitude": args.latitude,
            "longitude": args.longitude,
            "accuracy_meters": args.accuracy,
            "recorded_at": now,
        }))
    if args.event in ("sos", "all"):
        if not args.confirm_sos:
            raise ValueError("SOS creates an incident and queues notifications. Pass --confirm-sos to proceed.")
        data.append(("sos", "incidents/sos/", {
            "event_id": str(uuid.uuid4()),
            "trigger_source": "simulator",
        }))
    return data


def read_queue() -> list[dict]:
    if not QUEUE_PATH.exists():
        return []
    entries = []
    for line in QUEUE_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip():
            entries.append(json.loads(line))
    return entries


def write_queue(entries: list[dict]) -> None:
    QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_path = tempfile.mkstemp(prefix="device-queue-", dir=QUEUE_PATH.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            for entry in entries:
                stream.write(json.dumps(entry, separators=(",", ":")) + "\n")
        os.replace(temporary_path, QUEUE_PATH)
    finally:
        if os.path.exists(temporary_path):
            os.unlink(temporary_path)


def flush_queue(api_base: str, device_id: str, secret: str) -> int:
    entries = read_queue()
    remaining = []
    failures = 0
    for entry in entries:
        try:
            result = api_request(api_base, device_id, secret, entry["path"], entry["payload"])
            print(f"Queued {entry['kind']} event accepted: {json.dumps(result, separators=(',', ':'))}")
        except RuntimeError as error:
            failures += 1
            remaining.append(entry)
            print(f"Queued {entry['kind']} event remains pending: {error}", file=sys.stderr)
    write_queue(remaining)
    return failures


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send simulated device events to the Nexus Sync API.")
    parser.add_argument("--event", choices=("heartbeat", "measurement", "location", "sos", "all"), default="all")
    parser.add_argument("--api-base", default=os.getenv("NEXUS_API_BASE", "http://127.0.0.1:8000/api/v1"))
    parser.add_argument("--measurement-type", default="heart_rate_bpm", choices=("heart_rate_bpm", "spo2_percent", "skin_temperature_celsius"))
    parser.add_argument("--value", default="82")
    parser.add_argument("--unit", default="bpm")
    parser.add_argument("--latitude", default="5.6508", help="Simulator default is a test coordinate near UPSA.")
    parser.add_argument("--longitude", default="-0.1869")
    parser.add_argument("--accuracy", default="12")
    parser.add_argument("--battery", type=int, default=86)
    parser.add_argument("--firmware", default="simulator-1.0")
    parser.add_argument("--confirm-sos", action="store_true", help="Required because SOS creates an incident.")
    parser.add_argument("--flush-queue", action="store_true", help="Retry previously queued idempotent events before new events.")
    args = parser.parse_args()
    if args.measurement_type == "spo2_percent":
        args.unit = "percent"
    elif args.measurement_type == "skin_temperature_celsius":
        args.unit = "celsius"
    return args


def main() -> int:
    args = parse_args()
    device_id = os.getenv("NEXUS_DEVICE_ID", "").strip()
    secret = os.getenv("NEXUS_DEVICE_SECRET", "").strip()
    if not device_id or not secret:
        print("Set NEXUS_DEVICE_ID and NEXUS_DEVICE_SECRET in the environment (do not commit credentials).", file=sys.stderr)
        return 2
    if not args.api_base.startswith("https://") and not any(host in args.api_base for host in ("127.0.0.1", "localhost")):
        print("Use HTTPS for non-local API hosts.", file=sys.stderr)
        return 2

    failures = flush_queue(args.api_base, device_id, secret) if args.flush_queue else 0
    entries = read_queue()
    for kind, path, payload in event_payloads(args):
        entry = {"kind": kind, "path": path, "payload": payload}
        entries.append(entry)
        write_queue(entries)
        try:
            result = api_request(args.api_base, device_id, secret, path, payload)
            entries.pop()
            write_queue(entries)
            print(f"{kind} accepted: {json.dumps(result, separators=(',', ':'))}")
        except RuntimeError as error:
            failures += 1
            print(f"{kind} queued for retry: {error}", file=sys.stderr)
    print(f"Pending event count: {len(read_queue())}. Queue file: {QUEUE_PATH}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
