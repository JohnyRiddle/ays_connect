"""Start only the local Django dev service, passing validated iiko variables privately.

No migration/seed, production compose, credentials in argv, or credentials copied to repo.
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from iiko.config import ConfigurationError, Connection, read_env_file  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", required=True)
    args = parser.parse_args()
    try:
        values = read_env_file(args.env_file)
        config = Connection.from_env(values)
        if config.connection_id != "sheregesh":
            raise ConfigurationError("This local launcher is for sheregesh only.")
    except ConfigurationError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    environment = os.environ.copy()
    environment.update(values)
    environment["IIKO_SHEREGESH_ENV_FILE"] = ""
    command = ["docker", "compose", "-f", str(ROOT / "docker-compose.yml"), "run", "--rm", "--no-deps",
               "--service-ports", "--name", "aysconnect-iiko-dev"]
    for key in (*values, "IIKO_SHEREGESH_ENV_FILE"):
        command.extend(["-e", key])
    command.extend(["backend", "python", "manage.py", "runserver", "0.0.0.0:8000", "--noreload"])
    return subprocess.call(command, cwd=ROOT, env=environment)


if __name__ == "__main__":
    raise SystemExit(main())
