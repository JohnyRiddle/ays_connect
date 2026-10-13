from rest_framework import serializers


class TelegramStatusSerializer(serializers.Serializer):
    available = serializers.BooleanField()
    linked = serializers.BooleanField()
    username = serializers.CharField()
    linked_at = serializers.DateTimeField(allow_null=True)
    blocked = serializers.BooleanField()
    last_failure_code = serializers.CharField()
    last_delivery = serializers.DictField(allow_null=True)


class TelegramLinkSerializer(serializers.Serializer):
    bot_username = serializers.CharField()
    start_parameter = serializers.CharField()
    deep_link = serializers.CharField()
    expires_at = serializers.DateTimeField()


class TelegramUnlinkSerializer(serializers.Serializer):
    unlinked = serializers.BooleanField()
