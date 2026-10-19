import contextlib
import io
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from simulator import device_simulator


class DeviceSimulatorQueueTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.queue_path = Path(self.temporary_directory.name) / "queued-events.jsonl"
        self.queue_path_patcher = patch.object(device_simulator, "QUEUE_PATH", self.queue_path)
        self.queue_path_patcher.start()
        self.addCleanup(self.queue_path_patcher.stop)
        self.addCleanup(self.temporary_directory.cleanup)

    def queued_event(self):
        return {
            "kind": "measurement",
            "path": "measurements/",
            "payload": {"event_id": "stable-event-id", "value": "82"},
        }

    @patch.object(device_simulator, "api_request")
    def test_flush_success_sends_original_payload_and_removes_queue_entry(self, api_request):
        event = self.queued_event()
        device_simulator.write_queue([event])
        api_request.return_value = {"id": "accepted"}

        with contextlib.redirect_stdout(io.StringIO()):
            failures = device_simulator.flush_queue("https://example.test/api/v1", "device", "secret")

        self.assertEqual(failures, 0)
        api_request.assert_called_once_with(
            "https://example.test/api/v1",
            "device",
            "secret",
            "measurements/",
            event["payload"],
        )
        self.assertEqual(device_simulator.read_queue(), [])

    @patch.object(device_simulator, "api_request", side_effect=RuntimeError("offline"))
    def test_flush_failure_retains_event_and_event_id(self, api_request):
        event = self.queued_event()
        device_simulator.write_queue([event])

        with contextlib.redirect_stderr(io.StringIO()):
            failures = device_simulator.flush_queue("https://example.test/api/v1", "device", "secret")

        self.assertEqual(failures, 1)
        api_request.assert_called_once()
        self.assertEqual(device_simulator.read_queue(), [event])

    def test_queue_write_replaces_file_with_all_events(self):
        events = [self.queued_event(), {"kind": "location", "path": "locations/", "payload": {"event_id": "location-id"}}]

        device_simulator.write_queue(events)

        self.assertEqual(device_simulator.read_queue(), events)
        self.assertEqual(list(self.queue_path.parent.glob("device-queue-*")), [])


class DeviceSimulatorEventTests(unittest.TestCase):
    def test_sos_payload_requires_explicit_confirmation(self):
        args = Namespace(
            event="sos",
            confirm_sos=False,
            battery=86,
            firmware="simulator-1.0",
            measurement_type="heart_rate_bpm",
            value="82",
            unit="bpm",
            latitude="5.6508",
            longitude="-0.1869",
            accuracy="12",
        )

        with self.assertRaisesRegex(ValueError, "--confirm-sos"):
            device_simulator.event_payloads(args)

        args.confirm_sos = True
        kind, path, payload = device_simulator.event_payloads(args)[0]
        self.assertEqual((kind, path), ("sos", "incidents/sos/"))
        self.assertEqual(payload["trigger_source"], "simulator")
        self.assertTrue(payload["event_id"])


if __name__ == "__main__":
    unittest.main()
