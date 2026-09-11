from django.conf import settings
from django.db import models


class KnowledgeCategory(models.Model):
    name = models.CharField(max_length=180)
    slug = models.SlugField(max_length=190, unique=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="children")
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name_plural = "Категории базы знаний"

    def __str__(self):
        return self.name


class MaterialTag(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=90, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class KnowledgeMaterial(models.Model):
    class Type(models.TextChoices):
        BOOK = "BOOK", "Книга"
        PDF = "PDF", "PDF"
        PRESENTATION = "PRESENTATION", "Презентация"
        DOCUMENT = "DOCUMENT", "Документ"
        VIDEO = "VIDEO", "Видео"
        INSTRUCTION = "INSTRUCTION", "Инструкция"
        REGULATION = "REGULATION", "Регламент"
        POLICY = "POLICY", "Политика"
        TTK = "TTK", "ТТК"
        HACCP = "HACCP", "ХАССП"
        TECHNICAL_DOCUMENTATION = "TECHNICAL_DOCUMENTATION", "Техническая документация"
        TEMPLATE = "TEMPLATE", "Шаблон"
        IMAGE = "IMAGE", "Изображение"
        EXTERNAL_LINK = "EXTERNAL_LINK", "Внешняя ссылка"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Черновик"
        REVIEW = "REVIEW", "На проверке"
        PUBLISHED = "PUBLISHED", "Опубликован"
        NEEDS_UPDATE = "NEEDS_UPDATE", "Требует обновления"
        ARCHIVED = "ARCHIVED", "Архив"

    title = models.CharField(max_length=240)
    slug = models.SlugField(max_length=250, unique=True)
    description = models.TextField(blank=True)
    material_type = models.CharField(max_length=40, choices=Type.choices)
    category = models.ForeignKey(KnowledgeCategory, on_delete=models.PROTECT, related_name="materials")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_knowledge_materials")
    owner_department = models.ForeignKey("organizations.Department", on_delete=models.SET_NULL, null=True, blank=True, related_name="knowledge_materials")
    current_version = models.ForeignKey("MaterialVersion", on_delete=models.SET_NULL, null=True, blank=True, related_name="current_for_materials")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    language = models.CharField(max_length=12, default="ru")
    cover_image = models.FileField(upload_to="knowledge/covers/%Y/%m/", blank=True)
    is_required = models.BooleanField(default=False)
    is_downloadable = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    review_at = models.DateField(null=True, blank=True)
    tags = models.ManyToManyField(MaterialTag, blank=True, related_name="materials")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title


class MaterialVersion(models.Model):
    material = models.ForeignKey(KnowledgeMaterial, on_delete=models.CASCADE, related_name="versions")
    version = models.PositiveIntegerField()
    title = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to="knowledge/materials/%Y/%m/", blank=True)
    original_name = models.CharField(max_length=255, blank=True)
    content_type = models.CharField(max_length=120, blank=True)
    size = models.PositiveBigIntegerField(default=0)
    external_url = models.URLField(blank=True)
    content = models.TextField(blank=True)
    change_summary = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="knowledge_versions")
    created_at = models.DateTimeField(auto_now_add=True)
    effective_from = models.DateTimeField(null=True, blank=True)
    is_current = models.BooleanField(default=False)
    requires_reacknowledgment = models.BooleanField(default=False)

    class Meta:
        ordering = ["-version"]
        constraints = [models.UniqueConstraint(fields=["material", "version"], name="unique_material_version")]

    def __str__(self):
        return f"{self.material} v{self.version}"


class MaterialAccessRule(models.Model):
    class Level(models.TextChoices):
        VIEW = "VIEW", "Просмотр"
        DOWNLOAD = "DOWNLOAD", "Скачивание"
        EDIT = "EDIT", "Редактирование"
        MANAGE = "MANAGE", "Управление"

    material = models.ForeignKey(KnowledgeMaterial, on_delete=models.CASCADE, related_name="access_rules")
    employee = models.ForeignKey("employees.Employee", on_delete=models.CASCADE, null=True, blank=True, related_name="knowledge_access_rules")
    role = models.ForeignKey("accounts.Role", on_delete=models.CASCADE, null=True, blank=True, related_name="knowledge_access_rules")
    position = models.CharField(max_length=150, blank=True)
    department = models.ForeignKey("organizations.Department", on_delete=models.CASCADE, null=True, blank=True, related_name="knowledge_access_rules")
    facility = models.ForeignKey("organizations.Facility", on_delete=models.CASCADE, null=True, blank=True, related_name="knowledge_access_rules")
    region = models.ForeignKey("organizations.Region", on_delete=models.CASCADE, null=True, blank=True, related_name="knowledge_access_rules")
    access_level = models.CharField(max_length=12, choices=Level.choices, default=Level.VIEW)


class MaterialView(models.Model):
    material = models.ForeignKey(KnowledgeMaterial, on_delete=models.CASCADE, related_name="views")
    employee = models.ForeignKey("employees.Employee", on_delete=models.CASCADE, related_name="knowledge_views")
    version = models.ForeignKey(MaterialVersion, on_delete=models.SET_NULL, null=True, blank=True, related_name="views")
    viewed_at = models.DateTimeField(auto_now=True)
    view_count = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["material", "employee"], name="unique_material_employee_view")]


class MaterialFavorite(models.Model):
    material = models.ForeignKey(KnowledgeMaterial, on_delete=models.CASCADE, related_name="favorites")
    employee = models.ForeignKey("employees.Employee", on_delete=models.CASCADE, related_name="knowledge_favorites")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["material", "employee"], name="unique_material_employee_favorite")]


class MaterialAcknowledgmentAssignment(models.Model):
    class Status(models.TextChoices):
        ASSIGNED = "ASSIGNED", "Назначено"
        OPENED = "OPENED", "Открыто"
        ACKNOWLEDGED = "ACKNOWLEDGED", "Ознакомлен"
        OVERDUE = "OVERDUE", "Просрочено"
        CANCELLED = "CANCELLED", "Отменено"

    version = models.ForeignKey(MaterialVersion, on_delete=models.PROTECT, related_name="acknowledgment_assignments")
    employee = models.ForeignKey("employees.Employee", on_delete=models.CASCADE, related_name="material_acknowledgments")
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="assigned_material_acknowledgments")
    related_task = models.ForeignKey("tasks.Task", on_delete=models.SET_NULL, null=True, blank=True, related_name="material_acknowledgments")
    requires_test = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ASSIGNED)
    due_at = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["version", "employee"], name="unique_version_employee_acknowledgment")]


class TTKMetadata(models.Model):
    material = models.OneToOneField(KnowledgeMaterial, on_delete=models.CASCADE, related_name="ttk_metadata")
    dish_name = models.CharField(max_length=240, blank=True)
    dish_category = models.CharField(max_length=180, blank=True)
    brand = models.CharField(max_length=180, blank=True)
    facility = models.ForeignKey("organizations.Facility", on_delete=models.SET_NULL, null=True, blank=True, related_name="ttk_materials")
    workshop = models.CharField(max_length=180, blank=True)
    output_weight = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    yield_unit = models.CharField(max_length=32, blank=True)
    cooking_time_minutes = models.PositiveIntegerField(null=True, blank=True)
    storage_temperature = models.CharField(max_length=120, blank=True)
    storage_duration = models.CharField(max_length=120, blank=True)
    ingredients = models.JSONField(default=list, blank=True)
    technology = models.TextField(blank=True)
    storage_requirements = models.TextField(blank=True)
    allergens = models.JSONField(default=list, blank=True)
    serving_requirements = models.TextField(blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_ttk_materials")
    effective_from = models.DateTimeField(null=True, blank=True)
    reference_image = models.FileField(upload_to="knowledge/ttk/%Y/%m/", blank=True)
