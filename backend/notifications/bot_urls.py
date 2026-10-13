from django.urls import path
from . import bot_schema
from .bot_api import RedeemView, ClaimView, BeginView, AckView, FailView
urlpatterns = [path('bindings/redeem/', RedeemView.as_view()), path('deliveries/claim/', ClaimView.as_view()), path('deliveries/<int:pk>/begin/', BeginView.as_view()), path('deliveries/<int:pk>/ack/', AckView.as_view()), path('deliveries/<int:pk>/fail/', FailView.as_view())]
