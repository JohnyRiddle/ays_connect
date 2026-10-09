"""Read-only O0 inventory. Run with the target checkout's Django environment.

stdout contains aggregates only. --private-output must point outside the checkout;
it contains IDs and mapping candidates, and must never be committed.
No matching by name, data changes, migrations or seeds are performed.
"""
import argparse
from collections import Counter, defaultdict
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sys
import unicodedata


TARGETS = ("Location", "Facility", "Zone", "Region", "Cluster", "Company", "LegalEntity", "OrgUnit")


def normalize_name(value):
    return " ".join(unicodedata.normalize("NFKC", value or "").casefold().split())


def tree_issues(rows, parent_field="parent_id"):
    parents = {str(row["id"]): str(row[parent_field]) if row.get(parent_field) is not None else None for row in rows}
    cycles, visited = set(), set()
    missing = sorted(key for key, parent in parents.items() if parent and parent not in parents)
    for start in parents:
        path, positions = [], {}
        cursor = start
        while cursor in parents and cursor not in visited:
            if cursor in positions:
                cycles.add(tuple(sorted(path[positions[cursor]:])))
                break
            positions[cursor] = len(path)
            path.append(cursor)
            cursor = parents[cursor]
        visited.update(path)
    return {"cycles": [list(cycle) for cycle in sorted(cycles)], "missing_parent_ids": missing}


def duplicate_groups(rows, context_fields):
    groups = defaultdict(list)
    for row in rows:
        name = normalize_name(row.get("name"))
        if name:
            groups[(name, *(str(row.get(field)) for field in context_fields))].append(str(row["id"]))
    # Candidates only: never used to construct mapping.
    return [ids for ids in groups.values() if len(ids) > 1]


def facility_candidates(source, locations):
    """Corroborated proposals only. Never make a mapping decision from a name."""
    candidates = []
    for target in locations:
        evidence = []
        if source.get("code") and source["code"] == target.get("code"):
            evidence.append("same_nonempty_code_requires_confirmation")
        if normalize_name(source.get("name")) == normalize_name(target.get("name")) and normalize_name(source.get("address")) and normalize_name(source.get("address")) == normalize_name(target.get("address")):
            evidence.extend(["normalized_name", "normalized_address"])
        if evidence:
            candidates.append({"location_uuid": str(target["id"]), "evidence": evidence, "confirmation": "pending"})
    return candidates


@contextmanager
def readonly_snapshot(connection, transaction):
    if connection.vendor != "postgresql":
        raise RuntimeError("PostgreSQL is required; SQLite cannot close O0.")
    if connection.in_atomic_block:
        raise RuntimeError("Inventory requires its own top-level transaction.")
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            cursor.execute("SHOW transaction_read_only")
            if cursor.fetchone()[0] != "on":
                raise RuntimeError("Read-only transaction was not established.")
        try:
            yield
        finally:
            transaction.set_rollback(True)


def inventory():
    from django.apps import apps
    from django.db import connection, transaction
    from django.db.models import Count
    from django.db.migrations.loader import MigrationLoader

    with readonly_snapshot(connection, transaction):
        tables = set(connection.introspection.table_names())
        report = {"format_version": 1, "database_vendor": connection.vendor, "read_only": True,
                  "models": {}, "references": [], "unstructured_fields": [], "mapping": [], "errors": []}
        models = {name: apps.get_model("organizations", name) for name in TARGETS}
        target_labels = {model._meta.label for model in models.values()}
        dependency_counts = Counter()
        legal_contexts = defaultdict(set)
        source_rows = {}
        for name, model in models.items():
            if model._meta.db_table not in tables:
                report["errors"].append(f"missing_table:{model._meta.label}")
                continue
            fields = {field.name for field in model._meta.concrete_fields}
            selected = [field.attname for field in model._meta.concrete_fields
                        if field.name in {"id", "name", "code", "parent", "legal_entity", "location_type", "facility_type", "unit_type", "status", "is_active", "is_demo", "cluster", "region", "company", "facility", "timezone", "address"}]
            rows = list(model.objects.values(*selected))
            source_rows[name] = {str(row["id"]): row for row in rows}
            context = [field for field in ("parent_id", "cluster_id", "facility_id", "region_id", "company_id") if field in selected]
            report["models"][name] = {
                "count": len(rows), "blank_codes": sum(not (row.get("code") or "").strip() for row in rows) if "code" in fields else None,
                "blank_types": sum(not (row.get(next((f for f in ("location_type", "facility_type", "unit_type") if f in fields), "")) or "").strip() for row in rows) if fields & {"location_type", "facility_type", "unit_type"} else None,
                "null_legal_entities": sum(row.get("legal_entity_id") is None for row in rows) if "legal_entity" in fields else None,
                "active_distribution": dict(Counter(str(row.get("is_active")) for row in rows)) if "is_active" in fields else None,
                "status_distribution": dict(Counter(row.get("status") for row in rows)) if "status" in fields else None,
                "type_distribution": dict(Counter(row.get(next((f for f in ("location_type", "facility_type", "unit_type") if f in fields), "")) for row in rows)) if fields & {"location_type", "facility_type", "unit_type"} else None,
                "demo_count": sum(row.get("is_demo") is True for row in rows) if "is_demo" in fields else None,
                "duplicate_candidates": duplicate_groups(rows, context),
                "blank_names": sum(not normalize_name(row.get("name")) for row in rows),
                "blank_contexts": {key: sum(row.get(key) is None for row in rows) for key in context},
                "duplicate_nonempty_codes": [ids for ids in
                    duplicate_groups([dict(row, name=row.get("code")) for row in rows if (row.get("code") or "").strip()], [])] if "code" in fields else None,
                "tree": tree_issues(rows) if "parent" in fields else None,
            }
            for row in rows:
                if name in {"Location", "Facility", "Zone"}:
                    report["mapping"].append({"source_model": model._meta.label, "source_id": str(row["id"]),
                        "target_location_uuid": str(row["id"]) if name == "Location" else None,
                        "decision": "PRESERVE_UUID_CLASSIFICATION_PENDING" if name == "Location" else "UNRESOLVED",
                        "basis": "existing canonical identity" if name == "Location" else "requires business confirmation; never name-only",
                        "source_context": {key: str(row[key]) if row.get(key) is not None else None for key in context},
                        "existing_code": row.get("code"), "existing_type": row.get("location_type", row.get("facility_type")),
                        "confirmation": "pending", "conflicts": [], "dependent_records": 0})
                if name == "Location" and row.get("legal_entity_id"):
                    legal_contexts[str(row["id"])].add(str(row["legal_entity_id"]))

        for model in apps.get_models():
            if model._meta.db_table not in tables:
                continue
            for field in model._meta.concrete_fields:
                if field.is_relation and field.remote_field.model._meta.label in target_labels:
                    counts = list(model.objects.exclude(**{field.attname: None}).values(field.attname).annotate(total=Count("pk")))
                    report["references"].append({"model": model._meta.label, "field": field.name,
                    "target": field.remote_field.model._meta.label, "count": sum(row["total"] for row in counts),
                    "by_target": {str(row[field.attname]): row["total"] for row in counts}})
                    for row in counts:
                        dependency_counts[(field.remote_field.model._meta.label, str(row[field.attname]))] += row["total"]
                    if field.remote_field.model == models["Location"]:
                        context_field = next((f for f in model._meta.concrete_fields if f.name == "legal_entity" and f.is_relation), None)
                        if context_field:
                            for location_id, legal_id in model.objects.exclude(**{field.attname: None}).values_list(field.attname, context_field.attname).distinct():
                                if legal_id:
                                    legal_contexts[str(location_id)].add(str(legal_id))
                if field.get_internal_type() in {"JSONField", "TextField", "CharField"}:
                    # Values intentionally not exported: may contain PII or secrets.
                    report["unstructured_fields"].append({"model": model._meta.label, "field": field.name,
                        "type": field.get_internal_type(), "review": "semantic review required; not proof of absence"})
            for field in model._meta.private_fields:
                if field.__class__.__name__ == "GenericForeignKey":
                    report["unstructured_fields"].append({"model": model._meta.label, "field": field.name, "type": "GenericForeignKey", "review": "resolve content type and object ID privately"})
        for row in report["mapping"]:
            row["dependent_records"] = dependency_counts[(row["source_model"], row["source_id"])]
            if row["source_model"] == "organizations.Facility":
                row["candidate_locations"] = facility_candidates(source_rows["Facility"][row["source_id"]], source_rows.get("Location", {}).values())
                if len(row["candidate_locations"]) > 1:
                    row["conflicts"].append("multiple_corroborated_candidates")
            elif row["source_model"] == "organizations.Zone":
                row["candidate_locations"] = []
                row["conflicts"].append("parent_facility_mapping_not_confirmed")
        report["legacy_mapping_status"] = "N/A_FOR_THIS_SNAPSHOT_EMPTY_LEGACY" if not source_rows.get("Facility") and not source_rows.get("Zone") else "CANDIDATES_PENDING_REVIEW"
        report["multiple_legal_entity_candidates"] = {key: sorted(values) for key, values in legal_contexts.items() if len(values) > 1}
        loader = MigrationLoader(connection, ignore_no_migrations=True)
        report["applied_migrations"] = sorted(".".join(key) for key in loader.applied_migrations)
        report["unapplied_migrations"] = sorted(".".join(key) for key in set(loader.disk_migrations) - set(loader.applied_migrations))
        report["unknown_applied_migrations"] = sorted(".".join(key) for key in set(loader.applied_migrations) - set(loader.disk_migrations))
        report["o0_status"] = "BLOCKED_PENDING_DATA_PROVENANCE_AND_MAPPING_CONFIRMATION"
        return report


def public_summary(report):
    return {"read_only": report["read_only"], "o0_status": report["o0_status"],
        "models": {name: {key: value for key, value in data.items() if key in {"count", "blank_codes", "blank_types", "null_legal_entities", "demo_count", "active_distribution"}} | {
            "duplicate_candidate_groups": len(data["duplicate_candidates"]),
            "cycle_count": len((data["tree"] or {}).get("cycles", [])),
            "missing_parent_count": len((data["tree"] or {}).get("missing_parent_ids", [])),
        } for name, data in report["models"].items()},
        "reference_fields": len(report["references"]), "unstructured_fields_to_review": len(report["unstructured_fields"]),
        "multiple_legal_entity_candidates": len(report["multiple_legal_entity_candidates"]),
        "applied_migration_count": len(report["applied_migrations"]),
        "unapplied_migration_count": len(report["unapplied_migrations"]),
        "unknown_applied_migration_count": len(report["unknown_applied_migrations"]), "errors": report["errors"]}


def private_destination(value, repository):
    path = Path(value).resolve()
    if path == repository or repository in path.parents:
        raise ValueError("Private output must be outside the repository.")
    if path.exists():
        raise ValueError("Private output already exists; refusing overwrite.")
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-output")
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    output = private_destination(args.private_output, repository) if args.private_output else None
    sys.path.insert(0, str(repository / "backend"))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    report = inventory()
    if output:
        with output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2, default=str)
    print(json.dumps(public_summary(report), ensure_ascii=False, indent=2))
    return 2 if report["errors"] else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        # Never print connection settings, SQL or raw DB errors.
        print(json.dumps({"status": "INVENTORY_FAILED", "error_type": type(exc).__name__}), file=sys.stderr)
        sys.exit(2)
