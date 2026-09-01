from pathlib import Path
import unittest


class ProductionComposeRegressionTests(unittest.TestCase):
    def test_backup_script_does_not_require_host_executable_bit(self):
        compose = (Path(__file__).resolve().parent.parent / "docker-compose.prod.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("do sed 's/\\\\r$$//' /opt/ays/backup.sh | sh;", compose)
        self.assertNotIn("do sh /opt/ays/backup.sh;", compose)
        self.assertNotIn("do /opt/ays/backup.sh;", compose)


if __name__ == "__main__":
    unittest.main()
