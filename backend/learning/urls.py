from rest_framework.routers import DefaultRouter

from .views import AnswerOptionViewSet, AssessmentViewSet, AttemptViewSet, CertificateViewSet, AssignmentViewSet, CourseCategoryViewSet, CourseViewSet, LessonViewSet, QuestionViewSet

router = DefaultRouter()
router.register("categories", CourseCategoryViewSet, basename="course-category")
router.register("courses", CourseViewSet, basename="course")
router.register("assignments", AssignmentViewSet, basename="course-assignment")
router.register("lessons", LessonViewSet, basename="lesson")
router.register("assessments", AssessmentViewSet, basename="assessment")
router.register("questions", QuestionViewSet, basename="question")
router.register("answer-options", AnswerOptionViewSet, basename="answer-option")
router.register("attempts", AttemptViewSet, basename="assessment-attempt")
router.register("certificates", CertificateViewSet, basename="certificate")
urlpatterns = router.urls
