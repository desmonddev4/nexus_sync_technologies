from rest_framework import serializers


class DeviceHeartbeatSerializer(serializers.Serializer):
    battery_percent = serializers.IntegerField(min_value=0, max_value=100, required=False)
    firmware_version = serializers.CharField(max_length=40, required=False, allow_blank=True)