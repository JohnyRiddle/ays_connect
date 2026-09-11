import getpass
import hashlib
import json
import warnings
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from iiko.client import IikoClient, IikoError
from iiko.config import ConfigurationError, Connection, read_env_file


def catalog_summary(result):
    """Compare dictionary projections without dumping every organization's full catalog."""
    rows = []
    fingerprints = {"categories": set(), "programs": set()}
    for org in result["organizations"]:
        row = {"organizationId": org["organizationId"], "name": org["name"]}
        for method, key in (("categories", "guestCategories"), ("programs", "Programs")):
            data = org[method]
            if "error" in data:
                row[method] = data
                continue
            ordered = sorted(data[key], key=lambda i: str(i.get("id", "")))
            digest = hashlib.sha256(json.dumps(ordered, sort_keys=True).encode()).hexdigest()
            fingerprints[method].add(digest)
            row[method] = {"count": len(ordered), "sha256": digest}
        rows.append(row)
    return {"connectionId": result["connectionId"], "organizations": rows,
            "distinctCategoryCatalogs": len(fingerprints["categories"]),
            "distinctProgramCatalogs": len(fingerprints["programs"])}


class Command(BaseCommand):
    help = "Explicit read-only iiko checks. No writes; card number is entered privately at the terminal."
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument("operation", choices=("config", "auth", "organizations", "categories", "programs", "card", "catalogs"))
        parser.add_argument("--env-file", help="Local literal KEY=value file; never printed. Overrides environment entirely.")
        parser.add_argument("--organization", help="Explicit iiko organization UUID for categories/programs/card.")
        parser.add_argument("--card-file", help="Optional private UTF-8 file containing ONLY the user-selected test card number.")

    def handle(self, *args, **options):
        try:
            values = read_env_file(options["env_file"]) if options["env_file"] else None
            config = Connection.from_env(values)
            operation = options["operation"]
            if options["card_file"] and operation != "card":
                raise CommandError("--card-file is only valid for card.")
            if operation == "config":
                self.stdout.write("Configuration valid; credentials present. Values hidden. No network requests.")
                return
            client = IikoClient(config)
            if operation == "auth":
                result = client.authenticate()
            elif operation == "organizations":
                result = client.organizations()
            elif operation == "catalogs":
                # Only organization dictionaries, never bulk guests. Continue to distinguish access per operation.
                organizations = client.organizations()["organizations"]
                result = {"connectionId": config.connection_id, "organizations": []}
                failed = False
                for org in organizations:
                    row = {"organizationId": org["id"], "name": org.get("name")}
                    for method in ("categories", "programs"):
                        try:
                            row[method] = getattr(client, method)(org["id"])
                        except IikoError as exc:
                            failed = True
                            row[method] = {"error": str(exc)}
                    result["organizations"].append(row)
                self.stdout.write(json.dumps(catalog_summary(result), ensure_ascii=True, indent=2))
                if failed:
                    raise CommandError("Some dictionary operations failed; see individual safe results.")
                return
            else:
                if not options["organization"]:
                    raise CommandError("--organization is required; choose from organizations.")
                if operation == "card":
                    if options["card_file"]:
                        try:
                            with Path(options["card_file"]).open(encoding="utf-8-sig") as source:
                                content = source.read(1025)
                                if len(content) > 1024:
                                    raise CommandError("Private card input file is too large.")
                                number = content.strip()
                        except (OSError, UnicodeError):
                            raise CommandError("Cannot read private card input file.") from None
                    else:
                        with warnings.catch_warnings():
                            warnings.simplefilter("error", getpass.GetPassWarning)
                            try:
                                number = getpass.getpass("Test card number (hidden): ")
                            except (getpass.GetPassWarning, EOFError):
                                raise CommandError("A private interactive terminal is required for card input.") from None
                    result = client.card(options["organization"], number)
                else:
                    result = getattr(client, operation)(options["organization"])
            self.stdout.write(json.dumps(result, ensure_ascii=True, indent=2))
        except (ConfigurationError, IikoError) as exc:
            raise CommandError(str(exc)) from None
