from rest_framework import serializers

from .models import (AnswerOption, Assessment, AssessmentAttempt,
                     AssessmentResponse, Certificate, Course,
                     CourseAssignment, CourseAudience, CourseCategory,
                     CourseModule, Lesson, LessonProgress, Question)


class CourseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseCategory
        fields = ("id", "name", "slug", "description", "parent", "is_active", "sort_order")


class LessonSerializer(serializers.ModelSerializer):
    lesson_type_label = serializers.CharField(source="get_lesson_type_display", read_only=True)

    class Meta:
        model = Lesson
        fields = ("id", "module", "title", "lesson_type", "lesson_type_label", "content", "material", "video_url", "estimated_duration_minutes", "sort_order", "is_required", "requires_confirmation")


class CourseModuleSerializer(serializers.ModelSerializer):
    lessons = LessonSerializer(many=True, read_only=True)

    class Meta:
        model = CourseModule
        fields = ("id", "course", "title", "description", "sort_order", "is_required", "lessons")


class AudienceSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseAudience
        fields = ("id", "course", "employee", "role", "department", "facility", "position", "region", "is_required")
        read_only_fields = ("course",)

    def validate(self, attrs):
        if not any(attrs.get(key) for key in ("employee", "role", "department", "facility", "position", "region")):
            raise serializers.ValidationError("Укажите хотя бы один критерий аудитории")
        return attrs


class CourseListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    modules_count = serializers.IntegerField(read_only=True)
    lessons_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Course
        fields = ("id", "title", "slug", "short_description", "category", "category_name", "author", "owner_department", "is_mandatory", "estimated_duration_minutes", "passing_score", "max_attempts", "certificate_enabled", "status", "status_label", "version", "published_at", "modules_count", "lessons_count", "updated_at")


class CourseDetailSerializer(CourseListSerializer):
    modules = CourseModuleSerializer(many=True, read_only=True)
    audience_rules = AudienceSerializer(many=True, read_only=True)

    class Meta(CourseListSerializer.Meta):
        fields = CourseListSerializer.Meta.fields + ("description", "certificate_validity_days", "repeat_after_days", "modules", "audience_rules")


class CourseWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = ("title", "slug", "description", "short_description", "category", "owner_department", "is_mandatory", "estimated_duration_minutes", "passing_score", "max_attempts", "certificate_enabled", "certificate_validity_days", "repeat_after_days")

    def create(self, validated_data):
        validated_data["author"] = self.context["request"].user
        return super().create(validated_data)


class LessonProgressSerializer(serializers.ModelSerializer):
    lesson_title = serializers.CharField(source="lesson.title", read_only=True)

    class Meta:
        model = LessonProgress
        fields = ("id", "lesson", "lesson_title", "opened_at", "completed_at", "progress_percent", "confirmed", "confirmed_at", "time_spent_seconds")


class AssignmentSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source="course.title", read_only=True)
    employee_name = serializers.SerializerMethodField()
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    lesson_progress = LessonProgressSerializer(many=True, read_only=True)

    class Meta:
        model = CourseAssignment
        fields = ("id", "course", "course_title", "employee", "employee_name", "assigned_by", "assigned_at", "due_at", "started_at", "completed_at", "status", "status_label", "progress_percent", "current_lesson", "is_mandatory", "source", "related_task", "related_incident", "related_checklist", "comment", "lesson_progress")
        read_only_fields = ("assigned_by", "assigned_at", "started_at", "completed_at", "status", "progress_percent", "current_lesson", "lesson_progress")

    def get_employee_name(self, obj):
        user = obj.employee.user
        return user.get_full_name() or user.email if user else obj.employee.employee_number


class AnswerOptionPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnswerOption
        fields = ("id", "text", "image", "sort_order", "match_key")


class AnswerOptionAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnswerOption
        fields = ("id", "question", "text", "image", "is_correct", "sort_order", "match_key")


class QuestionPublicSerializer(serializers.ModelSerializer):
    options = AnswerOptionPublicSerializer(many=True, read_only=True)
    question_type_label = serializers.CharField(source="get_question_type_display", read_only=True)

    class Meta:
        model = Question
        fields = ("id", "text", "question_type", "question_type_label", "image", "points", "sort_order", "is_required", "options")


class QuestionAdminSerializer(serializers.ModelSerializer):
    options = AnswerOptionAdminSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = ("id", "assessment", "text", "question_type", "explanation", "image", "points", "sort_order", "is_required", "manual_review_required", "options")


class AssessmentSerializer(serializers.ModelSerializer):
    questions_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Assessment
        fields = ("id", "course", "title", "description", "time_limit_minutes", "passing_score", "max_attempts", "shuffle_questions", "shuffle_answers", "questions_per_attempt", "show_correct_answers", "allow_review", "manual_review_required", "is_active", "questions_count")


class ResponseSerializer(serializers.ModelSerializer):
    question_text = serializers.CharField(source="question.text", read_only=True)

    class Meta:
        model = AssessmentResponse
        fields = ("id", "question", "question_text", "selected_options", "text_answer", "number_answer", "is_correct", "points_awarded", "review_comment")
        read_only_fields = fields


class AttemptSerializer(serializers.ModelSerializer):
    questions = QuestionPublicSerializer(many=True, read_only=True)
    responses = ResponseSerializer(many=True, read_only=True)
    assessment_title = serializers.CharField(source="assessment.title", read_only=True)

    class Meta:
        model = AssessmentAttempt
        fields = ("id", "assessment", "assessment_title", "assignment", "employee", "started_at", "submitted_at", "status", "score", "max_score", "score_percent", "passed", "attempt_number", "time_spent_seconds", "reviewed_by", "reviewed_at", "review_comment", "questions", "responses")
        read_only_fields = fields


class CertificateSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source="course.title", read_only=True)

    class Meta:
        model = Certificate
        fields = ("id", "employee", "course", "course_title", "assignment", "certificate_number", "issued_at", "expires_at", "status", "verification_code", "issued_by")
        read_only_fields = fields
