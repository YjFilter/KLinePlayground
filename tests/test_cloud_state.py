import io
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from backend.cloud_state import CloudStateError, CloudUserArchiveStore


class FakeCursor:
    def __init__(self, database):
        self.database = database
        self._one = None
        self._all = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def execute(self, sql, params=None):
        normalized = " ".join(sql.split())
        self.database.statements.append((normalized, params))
        if normalized.startswith("INSERT INTO kline_user_archives"):
            username, payload = params
            previous = self.database.rows.get(username)
            revision = 1 if previous is None else previous[1] + 1
            self.database.rows[username] = (bytes(payload), revision)
            self._one = (revision,)
        elif normalized.startswith("SELECT payload, revision"):
            self._one = self.database.rows.get(params[0])
        elif normalized.startswith("SELECT username, payload"):
            self._all = [
                (username, payload)
                for username, (payload, _revision) in sorted(self.database.rows.items())
            ]
        elif normalized.startswith("DELETE FROM kline_user_archives"):
            username = params[0]
            self._one = (username,) if self.database.rows.pop(username, None) else None

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._all


class FakeConnection:
    def __init__(self, database):
        self.cursor_instance = FakeCursor(database)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def cursor(self):
        return self.cursor_instance


class FakeDatabase:
    def __init__(self):
        self.rows = {}
        self.statements = []
        self.urls = []

    def connect(self, url):
        self.urls.append(url)
        return FakeConnection(self)


def make_zip(entries):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return buffer.getvalue()


class CloudUserArchiveStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.users_dir = Path(self.temp_dir.name) / "users"
        self.database = FakeDatabase()

    def tearDown(self):
        self.temp_dir.cleanup()

    def make_store(self, env=None):
        return CloudUserArchiveStore(
            self.users_dir,
            environ=env or {"POSTGRES_URL": "postgresql://fake"},
            connect=self.database.connect,
        )

    def test_connection_url_uses_documented_environment_precedence(self):
        store = CloudUserArchiveStore(
            self.users_dir,
            environ={
                "DATABASE_URL_UNPOOLED": "postgresql://unpooled",
                "DATABASE_URL": "postgresql://database",
                "POSTGRES_URL": "postgresql://postgres",
            },
            connect=self.database.connect,
        )

        store.ensure_schema()

        self.assertTrue(store.enabled)
        self.assertEqual(self.database.urls, ["postgresql://postgres"])

    def test_store_is_disabled_without_connection_url(self):
        store = CloudUserArchiveStore(
            self.users_dir,
            environ={},
            connect=self.database.connect,
        )

        self.assertFalse(store.enabled)
        with self.assertRaisesRegex(CloudStateError, "disabled"):
            store.ensure_schema()
        self.assertEqual(self.database.urls, [])

    def test_save_user_creates_schema_archives_files_and_increments_revision(self):
        user_dir = self.users_dir / "alice"
        (user_dir / "nested").mkdir(parents=True)
        (user_dir / "profile.json").write_text('{"name":"alice"}', encoding="utf-8")
        (user_dir / "nested" / "orders.db").write_bytes(b"sqlite-content")
        store = self.make_store()

        first_revision = store.save_user("alice")
        (user_dir / "profile.json").write_text('{"name":"updated"}', encoding="utf-8")
        second_revision = store.save_user("alice")

        self.assertEqual((first_revision, second_revision), (1, 2))
        statements = "\n".join(sql for sql, _params in self.database.statements)
        self.assertIn("CREATE TABLE IF NOT EXISTS kline_user_archives", statements)
        self.assertIn("revision = kline_user_archives.revision + 1", statements)
        payload, revision = self.database.rows["alice"]
        self.assertEqual(revision, 2)
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            self.assertEqual(
                archive.read("profile.json").decode("utf-8"),
                '{"name":"updated"}',
            )
            self.assertEqual(archive.read("nested/orders.db"), b"sqlite-content")

    def test_save_user_rejects_symbolic_link_user_directory(self):
        store = self.make_store()
        user_dir = self.users_dir / "alice"

        with mock.patch.object(Path, "is_dir", return_value=True), mock.patch.object(
            Path,
            "is_symlink",
            side_effect=lambda path: path == user_dir,
            autospec=True,
        ):
            with self.assertRaisesRegex(CloudStateError, "symbolic link"):
                store.save_user("alice")

    def test_restore_user_replaces_existing_directory_from_archive(self):
        store = self.make_store()
        original = self.users_dir / "alice"
        original.mkdir(parents=True)
        (original / "stale.txt").write_text("stale", encoding="utf-8")
        self.database.rows["alice"] = (
            make_zip({"profile.json": "restored", "nested/order.txt": "order"}),
            7,
        )

        restored = store.restore_user("alice")

        self.assertTrue(restored)
        self.assertFalse((original / "stale.txt").exists())
        self.assertEqual((original / "profile.json").read_text(encoding="utf-8"), "restored")
        self.assertEqual((original / "nested" / "order.txt").read_text(encoding="utf-8"), "order")

    def test_restore_user_returns_false_when_archive_is_missing(self):
        store = self.make_store()

        self.assertFalse(store.restore_user("missing"))
        self.assertFalse((self.users_dir / "missing").exists())

    def test_restore_all_restores_each_archived_user(self):
        store = self.make_store()
        self.database.rows = {
            "alice": (make_zip({"one.txt": "1"}), 1),
            "bob": (make_zip({"two.txt": "2"}), 3),
        }

        restored = store.restore_all()

        self.assertEqual(restored, ["alice", "bob"])
        self.assertEqual((self.users_dir / "alice" / "one.txt").read_text(), "1")
        self.assertEqual((self.users_dir / "bob" / "two.txt").read_text(), "2")

    def test_delete_user_reports_whether_archive_existed(self):
        store = self.make_store()
        self.database.rows["alice"] = (b"payload", 1)

        self.assertTrue(store.delete_user("alice"))
        self.assertFalse(store.delete_user("alice"))

    def test_restore_rejects_zip_slip_without_touching_existing_user(self):
        store = self.make_store()
        original = self.users_dir / "alice"
        original.mkdir(parents=True)
        (original / "keep.txt").write_text("keep", encoding="utf-8")
        self.database.rows["alice"] = (make_zip({"../escaped.txt": "bad"}), 1)

        with self.assertRaisesRegex(CloudStateError, "unsafe archive path"):
            store.restore_user("alice")

        self.assertEqual((original / "keep.txt").read_text(), "keep")
        self.assertFalse((self.users_dir.parent / "escaped.txt").exists())

    def test_restore_failure_rolls_back_existing_directory(self):
        store = self.make_store()
        original = self.users_dir / "alice"
        original.mkdir(parents=True)
        (original / "keep.txt").write_text("keep", encoding="utf-8")
        self.database.rows["alice"] = (make_zip({"new.txt": "new"}), 1)
        real_replace = os.replace
        failed_target_replace = False

        def fail_staged_directory_replace(source, destination):
            nonlocal failed_target_replace
            source_path = Path(source)
            destination_path = Path(destination)
            if (
                not failed_target_replace
                and source_path.name == "content"
                and destination_path == original
            ):
                failed_target_replace = True
                raise OSError("simulated replace failure")
            return real_replace(source, destination)

        with mock.patch(
            "backend.cloud_state.os.replace",
            side_effect=fail_staged_directory_replace,
        ):
            with self.assertRaisesRegex(CloudStateError, "restore user 'alice'"):
                store.restore_user("alice")

        self.assertEqual((original / "keep.txt").read_text(), "keep")
        self.assertFalse((original / "new.txt").exists())

    def test_database_errors_are_wrapped_with_operation_context(self):
        def broken_connect(_url):
            raise RuntimeError("database unavailable")

        store = CloudUserArchiveStore(
            self.users_dir,
            environ={"DATABASE_URL": "postgresql://broken"},
            connect=broken_connect,
        )

        with self.assertRaisesRegex(CloudStateError, "initialize cloud archive schema") as caught:
            store.ensure_schema()
        self.assertIsInstance(caught.exception.__cause__, RuntimeError)

    def test_invalid_username_cannot_escape_users_directory(self):
        store = self.make_store()

        for username in ("../alice", "sub/alice", "sub\\alice", ".", ""):
            with self.subTest(username=username):
                with self.assertRaises(ValueError):
                    store.restore_user(username)


if __name__ == "__main__":
    unittest.main()
