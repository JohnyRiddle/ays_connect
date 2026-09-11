from rest_framework import serializers

from .models import (KnowledgeCategory, KnowledgeMaterial, MaterialAccessRule,
                     MaterialAcknowledgmentAssignment, MaterialFavorite,
                     MaterialTag, MaterialVersion, MaterialView, TTKMetadata)
from .services import validate_material_file


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = KnowledgeCategory
        fields = ("id", "name", "slug", "description", "parent", "is_active", "sort_order")


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaterialTag
        fields = ("id", "name", "slug")


class VersionSerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = MaterialVersion
        fields = ("id", "version", "title", "description", "original_name", "content_type", "size", "external_url", "content", "change_summary", "created_by", "created_at", "effective_from", "is_current", "requires_reacknowledgment", "download_url")
        read_only_fields = fields

    def get_download_url(self, obj):
        return f"/api/v1/knowledge/materials/{obj.material_id}/versions/{obj.id}/download/" if obj.file else None


class AccessRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaterialAccessRule
        fields = ("id", "employee", "role", "position", "department", "facility", "region", "access_level")

    def validate(self, attrs):
        if not any(attrs.get(key) for key in ("employee", "role", "position", "department", "facility", "region")):
            raise serializers.ValidationError("Укажите хотя бы один критерий доступа")
        return attrs


class TTKMetadataSerializer(serializers.ModelSerializer):
    facility_name = serializers.CharField(source="facility.name", read_only=True)
    approved_by_name = serializers.SerializerMethodField()

    class Meta:
        model = TTKMetadata
        fields = (
            "dish_name", "dish_category", "brand", "facility", "facility_name",
            "workshop", "output_weight", "yield_unit", "cooking_time_minutes",
            "storage_temperature", "storage_duration", "ingredients", "technology",
            "storage_requirements", "allergens", "serving_requirements", "approved_by",
            "approved_by_name", "effective_from", "reference_image",
        )

    def get_approved_by_name(self, obj) -> str:
        return obj.approved_by.get_full_name() if obj.approved_by else ""


class MaterialListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    material_type_label = serializers.CharField(source="get_material_type_display", read_only=True)
    current_version = VersionSerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    is_favorite = serializers.SerializerMethodField()

    class Meta:
        model = KnowledgeMaterial
        fields = ("id", "title", "slug", "description", "material_type", "material_type_label", "category", "category_name", "owner", "owner_department", "status", "language", "is_required", "is_downloadable", "is_featured", "published_at", "review_at", "current_version", "tags", "is_favorite", "created_at", "updated_at")

    def get_is_favorite(self, obj):
        employee = getattr(self.context["request"].user, "employee", None) if self.context.get("request") else None
        return bool(employee and obj.favorites.filter(employee=employee).exists())


class MaterialDetailSerializer(MaterialListSerializer):
    versions = VersionSerializer(many=True, read_only=True)
    access_rules = AccessRuleSerializer(many=True, read_only=True)
    ttk_metadata = TTKMetadataSerializer(read_only=True)

    class Meta(MaterialListSerializer.Meta):
        fields = MaterialListSerializer.Meta.fields + ("versions", "access_rules", "ttk_metadata")


class MaterialWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = KnowledgeMaterial
        fields = ("title", "slug", "description", "material_type", "category", "owner_department", "status", "language", "cover_image", "is_required", "is_downloadable", "is_featured", "review_at", "tags")
        read_only_fields = ("status",)

    def create(self, validated_data):
        validated_data["owner"] = self.context["request"].user
        return super().create(validated_data)


class VersionCreateSerializer(serializers.Serializer):
    title = serializers.CharField(required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    file = serializers.FileField(required=False)
    external_url = serializers.URLField(required=False, allow_blank=True)
    content = serializers.CharField(required=False, allow_blank=True)
    change_summary = serializers.CharField(required=False, allow_blank=True)
    effective_from = serializers.DateTimeField(required=False, allow_null=True)
    requires_reacknowledgment = serializers.BooleanField(default=False)

    def validate_file(self, value):
        validate_material_file(value)
        return value

    def validate(self, attrs):
        if not any(attrs.get(key) for key in ("file", "external_url", "content")):
            raise serializers.ValidationError("Добавьте файл, ссылку или текстовое содержимое")
        return attrs


class AcknowledgmentSerializer(serializers.ModelSerializer):
    material_id = serializers.IntegerField(source="version.material_id", read_only=True)
    material_title = serializers.CharField(source="version.material.title", read_only=True)
    version_number = serializers.IntegerField(source="version.version", read_only=True)

    class Meta:
        model = MaterialAcknowledgmentAssignment
        fields = ("id", "material_id", "material_title", "version", "version_number", "employee", "assigned_by", "related_task", "requires_test", "status", "due_at", "opened_at", "acknowledged_at", "created_at")
        read_only_fields = fields
