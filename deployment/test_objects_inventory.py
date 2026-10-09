import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

spec = importlib.util.spec_from_file_location("objects_inventory", Path(__file__).with_name("objects_inventory.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class InventoryTests(unittest.TestCase):
    def test_long_cycle_and_missing_parent(self):
        rows = [{"id": str(i), "parent_id": str((i + 1) % 1500)} for i in range(1500)]
        rows.append({"id": "orphan", "parent_id": "absent"})
        result = module.tree_issues(rows)
        self.assertEqual(len(result["cycles"]), 1)
        self.assertEqual(len(result["cycles"][0]), 1500)
        self.assertEqual(result["missing_parent_ids"], ["orphan"])

    def test_acyclic_shared_parent(self):
        self.assertEqual(module.tree_issues([{"id": "a", "parent_id": None}, {"id": "b", "parent_id": "a"}, {"id": "c", "parent_id": "a"}])["cycles"], [])

    def test_duplicate_is_candidate_only_and_uses_context(self):
        rows = [{"id": "a", "name": "  РЕСТОРАН  А ", "parent_id": "x"},
                {"id": "b", "name": "ресторан а", "parent_id": "x"},
                {"id": "c", "name": "ресторан а", "parent_id": "y"}]
        self.assertEqual(module.duplicate_groups(rows, ["parent_id"]), [["a", "b"]])

    def test_name_only_never_produces_mapping_candidate(self):
        source={"id":1,"name":"Same","address":"Address A"}
        self.assertEqual(module.facility_candidates(source,[{"id":"uuid","name":"Same","address":"Address B"}]),[])
        candidates=module.facility_candidates(source,[{"id":"uuid","name":" same ","address":" address a "}])
        self.assertEqual(candidates[0]["location_uuid"],"uuid")
        self.assertEqual(candidates[0]["confirmation"],"pending")

    def test_reject_private_export_inside_repository_and_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            with self.assertRaises(ValueError):
                module.private_destination(root / "dump.json", root)
            existing = root / "existing.json"
            existing.write_text("private", encoding="utf-8")
            with self.assertRaises(ValueError):
                module.private_destination(existing, root / "repo")

    def test_reject_sqlite_and_nested_transactions(self):
        for vendor, nested in [("sqlite", False), ("postgresql", True)]:
            connection = Mock(vendor=vendor, in_atomic_block=nested)
            with self.assertRaises(RuntimeError):
                with module.readonly_snapshot(connection, Mock()):
                    self.fail("must fail closed")

    def test_snapshot_checks_readonly_and_rolls_back_on_exception(self):
        connection = Mock(vendor="postgresql", in_atomic_block=False)
        cursor = Mock()
        connection.cursor.return_value.__enter__ = Mock(return_value=cursor)
        connection.cursor.return_value.__exit__ = Mock(return_value=False)
        cursor.fetchone.return_value = ("on",)
        transaction = Mock()
        transaction.atomic.return_value.__enter__ = Mock()
        transaction.atomic.return_value.__exit__ = Mock(return_value=False)
        with self.assertRaises(ValueError):
            with module.readonly_snapshot(connection, transaction):
                raise ValueError("synthetic failure")
        self.assertEqual(cursor.execute.call_args_list[0].args[0], "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        transaction.set_rollback.assert_called_once_with(True)

    def test_public_summary_does_not_export_ids_or_names(self):
        report = {"read_only": True, "o0_status": "BLOCKED", "models": {"Location": {"count": 2,
            "duplicate_candidates": [["private-id", "secret-id"]], "tree": {"cycles": [["private-id"]], "missing_parent_ids": []},
            "type_distribution": {"private-name": 2}}}, "references": [], "unstructured_fields": [],
            "multiple_legal_entity_candidates": {"private-id": ["secret-id"]}, "applied_migrations": [],
            "unapplied_migrations": [], "unknown_applied_migrations": [], "errors": []}
        summary = str(module.public_summary(report))
        for secret in ("private-id", "secret-id", "private-name"):
            self.assertNotIn(secret, summary)


if __name__ == "__main__":
    unittest.main()
