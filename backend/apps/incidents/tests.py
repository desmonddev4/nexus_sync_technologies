import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.incidents.models import Incident, IncidentEvent
from apps.incidents.services import InvalidIncidentTransition, transition_incident
from apps.patients.models import Patient


class IncidentServiceTests(TestCase):
    def setUp(self):
        self.patient = Patient.objects.create(full_name="SOS Test Patient")
        self.actor = get_user_model().objects.create_user(username="operator")

    def test_acknowledgement_updates_state_and_preserves_event_history(self):
        incident = Incident.objects.create(
            patient=self.patient,
            source_event_id=uuid.uuid4(),
            trigger_source=Incident.Source.MANUAL,
        )

        updated = transition_incident(
            incident=incident,
            new_status=Incident.Status.ACKNOWLEDGED,
            actor=self.actor,
        )

        self.assertEqual(updated.status, Incident.Status.ACKNOWLEDGED)
        self.assertEqual(IncidentEvent.objects.filter(incident=incident).count(), 1)

    def test_closed_incident_cannot_be_acknowledged(self):
        incident = Incident.objects.create(
            patient=self.patient,
            source_event_id=uuid.uuid4(),
            trigger_source=Incident.Source.MANUAL,
            status=Incident.Status.CLOSED,
        )

        with self.assertRaises(InvalidIncidentTransition):
            transition_incident(
                incident=incident,
                new_status=Incident.Status.ACKNOWLEDGED,
                actor=self.actor,
            )