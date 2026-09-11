import math
import os
import re
from dataclasses import dataclass, field
from pathlib import Path


class ConfigurationError(Exception):
    pass


ENV_FIELDS = (
    "IIKO_CONNECTION_ID", "IIKO_APP_ID", "IIKO_CLIENT_SECRET", "IIKO_API_KEY",
    "IIKO_BASE_URL", "IIKO_CONNECT_TIMEOUT", "IIKO_READ_TIMEOUT", "IIKO_MAX_RETRIES",
)


def read_env_file(path):
    """Deliberately small dotenv subset: literal KEY=value, no interpolation/code."""
    values = {}
    try:
        lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeError):
        raise ConfigurationError("Cannot read local iiko configuration file.") from None
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, value = line.partition("=")
        key = key.strip()
        if not sep or key not in ENV_FIELDS or key in values:
            raise ConfigurationError("Invalid or duplicate configuration field.")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key] = value
    return values


@dataclass(frozen=True)
class Connection:
    connection_id: str
    app_id: str = field(repr=False)
    client_secret: str = field(repr=False)
    api_key: str = field(repr=False)
    base_url: str = "https://api-ru.iiko.services"
    connect_timeout: float = 5
    read_timeout: float = 20
    max_retries: int = 2

    def __post_init__(self):
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", self.connection_id):
            raise ConfigurationError("IIKO_CONNECTION_ID must be a lowercase location slug.")
        for value in (self.app_id, self.client_secret, self.api_key):
            if not value or any(ord(c) < 32 for c in value):
                raise ConfigurationError("Missing or invalid iiko credentials.")
        # Credentials must never be sent to arbitrary hosts or redirected endpoints.
        if self.base_url != "https://api-ru.iiko.services":
            raise ConfigurationError("Unsupported IIKO_BASE_URL; only the verified RU HTTPS endpoint is allowed.")
        if any(not math.isfinite(t) or not 0 < t <= 120 for t in (self.connect_timeout, self.read_timeout)):
            raise ConfigurationError("Timeouts must be finite and between 0 and 120 seconds.")
        if type(self.max_retries) is not int or not 0 <= self.max_retries <= 2:
            raise ConfigurationError("IIKO_MAX_RETRIES must be 0, 1 or 2.")

    @classmethod
    def from_env(cls, values=None):
        values = os.environ if values is None else values
        missing = [k for k in ENV_FIELDS[:4] if not values.get(k, "").strip()]
        if missing:
            raise ConfigurationError("Missing fields: " + ", ".join(missing))
        try:
            connect = float(values.get("IIKO_CONNECT_TIMEOUT") or 5)
            read = float(values.get("IIKO_READ_TIMEOUT") or 20)
            retries = int(values.get("IIKO_MAX_RETRIES") or 2)
        except (ValueError, TypeError):
            raise ConfigurationError("Invalid timeout/retry configuration.") from None
        return cls(values["IIKO_CONNECTION_ID"], values["IIKO_APP_ID"],
                   values["IIKO_CLIENT_SECRET"], values["IIKO_API_KEY"],
                   values.get("IIKO_BASE_URL") or "https://api-ru.iiko.services",
                   connect, read, retries)
