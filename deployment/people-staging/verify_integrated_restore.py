"""Compare a restored integrated synthetic database and media tree to its source."""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

sys.path.insert(0, "/app")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.db import IntegrityError, connections, transaction


source_name = os.environ.get("INTEGRATED_SOURCE_DB", "integrated_upgrade_20260927")
restore_name = os.environ.get("INTEGRATED_RESTORE_DB", "integrated_restore_20260927")
if not source_name.startswith("integrated_upgrade_") or not restore_name.startswith(
    "integrated_restore_"
):
    raise RuntimeError("Refusing non-synthetic database names")

for alias, name in (("source", source_name), ("restore", restore_name)):
    config = connections.databases["default"].copy()
    config["NAME"] = name
    connections.databases[alias] = config


def database_fingerprint(alias: str):
    with connections[alias].cursor() as cursor:
        cursor.execute(
            "SELECT tablename FROM pg_tables "
            "WHERE schemaname='public' ORDER BY tablename"
        )
        tables = [row[0] for row in cursor.fetchall()]
        result = {}
        for table in tables:
            cursor.execute(f'SELECT row_to_json(t)::text FROM "{table}" t')
            rows = sorted(row[0] for row in cursor.fetchall())
            result[table] = (
                len(rows),
                hashlib.sha256("\n".join(rows).encode()).hexdigest(),
            )
    return result


def media_fingerprint(root: Path):
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


source = database_fingerprint("source")
restored = database_fingerprint("restore")
assert source == restored, "restored integrated database differs from source"

source_media = Path(os.environ.get("INTEGRATED_SOURCE_MEDIA", "/synthetic-media-source"))
restore_media = Path(os.environ.get("INTEGRATED_RESTORE_MEDIA", "/synthetic-media-restore"))
assert media_fingerprint(source_media) == media_fingerprint(restore_media)

from projects.models import Project

project = Project.objects.using("restore").get(number="PRJ-UPGRADE-1")
try:
    with transaction.atomic(using="restore"):
        Project.objects.using("restore").filter(pk=project.pk).update(
            number="PRJ-RESTORE-BYPASS"
        )
except IntegrityError:
    pass
else:
    raise AssertionError("restored project number guard did not reject the update")

assert database_fingerprint("restore") == source, "guard probe changed restored DB"
print("INTEGRATED_RESTORE_PASS")
print(
    f"tables={len(source)} rows={sum(item[0] for item in source.values())} "
    f"media_files={len(media_fingerprint(source_media))}"
)
