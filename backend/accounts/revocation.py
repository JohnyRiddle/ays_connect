from django.db.models import F
from rest_framework.exceptions import AuthenticationFailed


def require_current_credentials(user, token):
    # Existing signed tokens have implicit generation zero. They remain valid
    # only until the first revoke; missing claims can never bypass later revokes.
    version = token.get("auth_version", 0)
    if type(version) is not int or version != user.auth_version:
        raise AuthenticationFailed("Account is unavailable.", code="account_unavailable")


def revoke_credentials(user):
    """Called inside the Employee lifecycle transaction, after its row lock."""
    type(user).objects.filter(pk=user.pk).update(auth_version=F("auth_version") + 1)
    user.refresh_from_db(fields=["auth_version"])
