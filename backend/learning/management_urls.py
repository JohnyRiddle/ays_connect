from django.urls import path

from .management_views import (
    AcknowledgmentManagementView,
    EmployeeLearningView,
    ExpiringCertificatesView,
    KnowledgeAnalyticsView,
    LearningSummaryView,
    OverdueLearningView,
)

urlpatterns = [
    path("learning/summary/", LearningSummaryView.as_view(), name="management-learning-summary"),
    path("learning/employees/", EmployeeLearningView.as_view(), name="management-learning-employees"),
    path("learning/overdue/", OverdueLearningView.as_view(), name="management-learning-overdue"),
    path("certificates/expiring/", ExpiringCertificatesView.as_view(), name="management-certificates-expiring"),
    path("knowledge/acknowledgments/", AcknowledgmentManagementView.as_view(), name="management-knowledge-acknowledgments"),
    path("knowledge/analytics/", KnowledgeAnalyticsView.as_view(), name="management-knowledge-analytics"),
]
