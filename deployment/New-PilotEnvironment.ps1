param([string]$Path = ".env.pilot")

$ErrorActionPreference = "Stop"
if (Test-Path -LiteralPath $Path) {
    throw "Environment file already exists: $Path"
}

function New-Secret([int]$Bytes = 48) {
    $buffer = New-Object byte[] $Bytes
    [Security.Cryptography.RandomNumberGenerator]::Fill($buffer)
    return [Convert]::ToBase64String($buffer).Replace("+", "-").Replace("/", "_").TrimEnd("=")
}

$content = @"
DJANGO_SECRET_KEY=$(New-Secret 64)
POSTGRES_DB=ays_connect_pilot
POSTGRES_USER=ays_pilot
POSTGRES_PASSWORD=$(New-Secret 36)
PILOT_HOST=localhost
DJANGO_ALLOWED_HOSTS=localhost,backend
CSRF_TRUSTED_ORIGINS=https://localhost
CORS_ALLOWED_ORIGINS=https://localhost
AYS_CONNECT_PUBLIC_URL=https://localhost
AYS_CONNECT_VERSION=local-pilot
DJANGO_SECURE_HSTS_SECONDS=0
NOTIFICATIONS_TELEGRAM_ENABLED=0
TELEGRAM_BOT_TOKEN=
TELEGRAM_BOT_USERNAME=
TELEGRAM_WEBHOOK_SECRET=$(New-Secret 32)
TELEGRAM_WEBHOOK_URL=
NOTIFICATIONS_EMAIL_ENABLED=0
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=
EMAIL_PORT=587
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
EMAIL_USE_TLS=1
DEFAULT_FROM_EMAIL=AYS Connect <no-reply@localhost>
BACKUP_RETENTION_DAYS=7
"@

[IO.File]::WriteAllText((Join-Path (Get-Location) $Path), $content, [Text.UTF8Encoding]::new($false))
Write-Host "Created $Path with generated local pilot secrets."
