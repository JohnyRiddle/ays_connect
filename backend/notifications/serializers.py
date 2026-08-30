from rest_framework import serializers
from .models import Notification,NotificationDelivery,NotificationPreference,NotificationQuietHours,NotificationTemplate
from .services import validate_template,validate_timezone
class NotificationSerializer(serializers.ModelSerializer):
    type_label=serializers.CharField(source="get_notification_type_display",read_only=True)
    class Meta:model=Notification;fields=("id","notification_type","type_label","priority","title","message","entity_type","entity_id","action_url","is_read","read_at","delivered_at","created_at")
class TemplateSerializer(serializers.ModelSerializer):
    def validate(self,a):
        allowed=a.get("allowed_variables",getattr(self.instance,"allowed_variables",[]));validate_template(a.get("title_template",getattr(self.instance,"title_template","")),allowed);validate_template(a.get("body_template",getattr(self.instance,"body_template","")),allowed);return a
    class Meta:model=NotificationTemplate;fields="__all__";read_only_fields=("created_at","updated_at")
class PreferenceSerializer(serializers.ModelSerializer):
    class Meta:model=NotificationPreference;fields=("id","reason","channel","enabled")
class QuietHoursSerializer(serializers.ModelSerializer):
    timezone=serializers.CharField(validators=[validate_timezone])
    class Meta:model=NotificationQuietHours;fields=("enabled","timezone","starts_at","ends_at")
class DeliverySerializer(serializers.ModelSerializer):
    class Meta:model=NotificationDelivery;fields=("id","notification","channel","status","attempts","next_attempt_at","delivered_at","last_error","last_error_code","provider_message_id","provider_metadata","routing_snapshot","created_at");read_only_fields=fields
