import json
import smtplib
import urllib.error
import urllib.request
from dataclasses import dataclass,field
from django.conf import settings
from django.core.mail import EmailMessage
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import NotificationChannelTemplate,TelegramAccount
from .services import render_template

@dataclass
class ProviderResult:
    message_id:str="";metadata:dict=field(default_factory=dict)
class ProviderFailure(Exception):
    def __init__(self,code,message="",retryable=False,retry_after=None,ambiguous=False):super().__init__(message or code);self.code=code;self.retryable=retryable;self.retry_after=retry_after;self.ambiguous=ambiguous

class TelegramBotClient:
    def __init__(self,token=None,timeout=None):self.token=token or settings.TELEGRAM_BOT_TOKEN;self.timeout=timeout or settings.TELEGRAM_HTTP_TIMEOUT
    def call(self,method,payload):
        if not self.token:raise ProviderFailure("TELEGRAM_NOT_CONFIGURED")
        request=urllib.request.Request(f"https://api.telegram.org/bot{self.token}/{method}",data=json.dumps(payload).encode(),headers={"Content-Type":"application/json"},method="POST")
        try:
            with urllib.request.urlopen(request,timeout=self.timeout) as response:data=json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            try:data=json.loads(exc.read().decode())
            except Exception:data={}
            description=str(data.get("description","")).lower();retry_after=(data.get("parameters") or {}).get("retry_after")
            if exc.code==429:raise ProviderFailure("TELEGRAM_RATE_LIMITED",retryable=True,retry_after=retry_after)
            if exc.code>=500:raise ProviderFailure("TELEGRAM_PROVIDER_UNAVAILABLE",retryable=True)
            if exc.code==401:raise ProviderFailure("TELEGRAM_UNAUTHORIZED")
            if "blocked" in description:raise ProviderFailure("TELEGRAM_BOT_BLOCKED")
            if "chat not found" in description:raise ProviderFailure("TELEGRAM_CHAT_NOT_FOUND")
            raise ProviderFailure("TELEGRAM_REJECTED")
        except (TimeoutError,urllib.error.URLError,ConnectionError) as exc:raise ProviderFailure("TELEGRAM_NETWORK_ERROR",str(exc),retryable=True,ambiguous=True) from exc
        if not data.get("ok"):raise ProviderFailure("TELEGRAM_REJECTED")
        return data.get("result") or {}
    def send_message(self,chat_id,text):
        result=self.call("sendMessage",{"chat_id":chat_id,"text":text,"disable_web_page_preview":True});return ProviderResult(str(result.get("message_id","") or ""),{"provider_date":result.get("date")})
    def set_webhook(self,url,secret):return self.call("setWebhook",{"url":url,"secret_token":secret})

def channel_content(notification,channel):
    specific=NotificationChannelTemplate.objects.filter(template=notification.template,channel=channel,is_active=True).first() if notification.template_id else None
    payload=notification.intent.payload if notification.intent_id else {}
    if specific:
        allowed=notification.template.allowed_variables;subject=render_template(specific.subject_template,payload,allowed) if specific.subject_template else notification.title;body=render_template(specific.body_template,payload,allowed)
    else:subject,body=notification.title,notification.message
    subject=subject.replace("\r"," ").replace("\n"," ")[:200]
    public_url=settings.AYS_CONNECT_PUBLIC_URL.rstrip("/")
    link=f"{public_url}{notification.action_url}" if public_url and notification.action_url else ""
    return subject,body+(f"\n\n{link}" if link else "")

class InAppChannelHandler:
    def send(self,delivery):return ProviderResult()
class TelegramChannelHandler:
    def __init__(self,client=None):self.client=client or TelegramBotClient()
    def send(self,delivery):
        account=TelegramAccount.objects.filter(employee=delivery.notification.recipient_employee,is_active=True,delivery_disabled_at__isnull=True).first()
        if not account:raise ProviderFailure("RECIPIENT_NOT_LINKED")
        title,body=channel_content(delivery.notification,"telegram")
        try:result=self.client.send_message(account.telegram_chat_id,f"{title}\n\n{body}")
        except ProviderFailure as exc:
            account.last_failure_at=timezone.now();account.last_failure_code=exc.code
            if exc.code in {"TELEGRAM_BOT_BLOCKED","TELEGRAM_CHAT_NOT_FOUND"}:account.delivery_disabled_at=account.last_failure_at
            account.save(update_fields=["last_failure_at","last_failure_code","delivery_disabled_at","updated_at"]);raise
        account.last_success_at=timezone.now();account.last_failure_code="";account.save(update_fields=["last_success_at","last_failure_code","updated_at"]);result.metadata["telegram_account_id"]=str(account.pk);return result
class DjangoEmailProvider:
    def send(self,recipient,subject,text_body):
        try:validate_email(recipient)
        except ValidationError as exc:raise ProviderFailure("RECIPIENT_EMAIL_INVALID") from exc
        try:
            sent=EmailMessage(subject=subject,body=text_body,from_email=settings.DEFAULT_FROM_EMAIL,to=[recipient]).send(fail_silently=False)
        except smtplib.SMTPResponseException as exc:raise ProviderFailure("EMAIL_TEMPORARY_REJECTION" if 400<=exc.smtp_code<500 else "EMAIL_PERMANENT_REJECTION",retryable=400<=exc.smtp_code<500) from exc
        except (smtplib.SMTPException,ConnectionError,TimeoutError,OSError) as exc:raise ProviderFailure("EMAIL_PROVIDER_ERROR",str(exc),retryable=True,ambiguous=True) from exc
        if sent!=1:raise ProviderFailure("EMAIL_NOT_ACCEPTED",ambiguous=True)
        return ProviderResult()
class EmailChannelHandler:
    def __init__(self,provider=None):self.provider=provider or DjangoEmailProvider()
    def send(self,delivery):
        recipient=delivery.notification.recipient.email
        if not recipient:raise ProviderFailure("RECIPIENT_EMAIL_MISSING")
        subject,body=channel_content(delivery.notification,"email");return self.provider.send(recipient,subject,body)
CHANNEL_HANDLERS={"in_app":InAppChannelHandler,"telegram":TelegramChannelHandler,"email":EmailChannelHandler}
