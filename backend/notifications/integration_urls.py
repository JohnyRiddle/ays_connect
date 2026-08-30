from django.urls import path
from .channel_views import TelegramWebhookView
urlpatterns=[path("webhook/",TelegramWebhookView.as_view())]
