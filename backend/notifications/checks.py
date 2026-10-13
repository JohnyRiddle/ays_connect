from django.conf import settings
from django.core.checks import Warning,register
@register()
def notification_configuration(app_configs,**kwargs):
    warnings=[]
    if settings.NOTIFICATIONS_TELEGRAM_ENABLED and settings.TELEGRAM_DELIVERY_TRANSPORT == 'direct' and not settings.TELEGRAM_BOT_TOKEN:warnings.append(Warning("Telegram notifications enabled but TELEGRAM_BOT_TOKEN is missing",id="notifications.W001"))
    if settings.NOTIFICATIONS_TELEGRAM_ENABLED and settings.TELEGRAM_DELIVERY_TRANSPORT == 'direct' and not settings.TELEGRAM_WEBHOOK_SECRET:warnings.append(Warning("Telegram notifications enabled but TELEGRAM_WEBHOOK_SECRET is missing",id="notifications.W002"))
    from django.core.checks import Error
    if settings.TELEGRAM_DELIVERY_TRANSPORT not in {'direct', 'pull'}:
        warnings.append(Error('Unsupported Telegram transport', id='notifications.E001'))
    if settings.TELEGRAM_BOT_LEASE_SECONDS <= 0 or settings.TELEGRAM_LINK_TOKEN_TTL <= 0:
        warnings.append(Error('Telegram TTL values must be positive', id='notifications.E002'))
    if any(value is not None and value <= 0 for value in settings.WORK_TASK_PRIORITY_HOURS.values()):
        warnings.append(Error('Task priority durations must be positive', id='notifications.E003'))
    if settings.TELEGRAM_BOT_SERVICE_ENABLED:
        digest = settings.TELEGRAM_BOT_SERVICE_TOKEN_SHA256
        if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
            warnings.append(Error('Set SHA256 of a separate corporate bot service credential', id='notifications.E004'))
    return warnings
