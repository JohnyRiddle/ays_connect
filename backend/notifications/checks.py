from django.conf import settings
from django.core.checks import Warning,register
@register()
def notification_configuration(app_configs,**kwargs):
    warnings=[]
    if settings.NOTIFICATIONS_TELEGRAM_ENABLED and not settings.TELEGRAM_BOT_TOKEN:warnings.append(Warning("Telegram notifications enabled but TELEGRAM_BOT_TOKEN is missing",id="notifications.W001"))
    if settings.NOTIFICATIONS_TELEGRAM_ENABLED and not settings.TELEGRAM_WEBHOOK_SECRET:warnings.append(Warning("Telegram notifications enabled but TELEGRAM_WEBHOOK_SECRET is missing",id="notifications.W002"))
    return warnings
