"""Local acceptance entrypoint; generated credentials never enter logs or Git."""
import os
from pathlib import Path
import secrets
import sys

secret = Path('/staging-private/django-key')
try:
    with secret.open('x') as stream:
        stream.write(secrets.token_urlsafe(64))
    secret.chmod(0o600)
except FileExistsError:
    pass
os.environ['DJANGO_SECRET_KEY'] = secret.read_text()
os.execvp(sys.argv[1], sys.argv[1:])
