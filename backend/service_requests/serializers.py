from rest_framework import serializers
from .models import ServiceCategory, Service, RequestType, RequestTypeAccessRule, RequestFieldDefinition, RequestFieldOption, RequestTypeSchemaVersion


class CategorySerializer(serializers.ModelSerializer):
    class Meta: model=ServiceCategory; fields="__all__"; read_only_fields=("id","created_at","updated_at")
class ServiceSerializer(serializers.ModelSerializer):
    class Meta: model=Service; fields="__all__"; read_only_fields=("id","created_at","updated_at")
class AccessRuleSerializer(serializers.ModelSerializer):
    class Meta: model=RequestTypeAccessRule; fields="__all__"; read_only_fields=("id","created_at","request_type")
    def validate(self,data):
        scope=data.get("scope_type"); mapping={"legal_entity":"legal_entity","org_unit":"org_unit","location":"location","role":"role"}
        populated=[name for name in ("legal_entity","org_unit","location","role") if data.get(name)]
        expected=mapping.get(scope)
        if scope=="global" and populated: raise serializers.ValidationError("GLOBAL rule cannot have a target.")
        if expected and populated!=[expected]: raise serializers.ValidationError(f"{scope} rule requires only {expected}.")
        return data
class OptionSerializer(serializers.ModelSerializer):
    class Meta: model=RequestFieldOption; fields="__all__"; read_only_fields=("id","created_at","updated_at","field")
class FieldSerializer(serializers.ModelSerializer):
    options=OptionSerializer(many=True,read_only=True)
    class Meta: model=RequestFieldDefinition; fields="__all__"; read_only_fields=("id","created_at","updated_at","request_type")
class SchemaVersionSerializer(serializers.ModelSerializer):
    class Meta: model=RequestTypeSchemaVersion; fields="__all__"; read_only_fields=("id","request_type","version","schema_json","created_by","created_at")
class RequestTypeSerializer(serializers.ModelSerializer):
    current_schema_version_number=serializers.IntegerField(source="current_schema_version.version",read_only=True)
    class Meta:
        model=RequestType; fields="__all__"
        read_only_fields=("id","created_at","updated_at","created_by","current_schema_version")
