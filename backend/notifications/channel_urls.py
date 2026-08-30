from django.urls import path
from .channel_views import ChannelStatusView,DeliveryDiagnosticsView,SelfPreferencesView,SelfQuietHoursView,TelegramLinkView,TelegramStatusView,TelegramUnlinkView
urlpatterns=[path("",ChannelStatusView.as_view()),path("telegram/",TelegramStatusView.as_view()),path("telegram/link/",TelegramLinkView.as_view()),path("telegram/unlink/",TelegramUnlinkView.as_view()),path("preferences/",SelfPreferencesView.as_view()),path("quiet-hours/",SelfQuietHoursView.as_view()),path("deliveries/",DeliveryDiagnosticsView.as_view())]
