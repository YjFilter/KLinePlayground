"""PostgreSQL-backed archives for per-user local state directories."""

from __future__ import annotations

import io
import os
import shutil
import stat
import tempfile
import threading
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from typing import Callable, Mapping, Optional


class CloudStateError(RuntimeError):
    """Raised when a cloud archive operation cannot complete safely."""


_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS kline_user_archives (
    username text PRIMARY KEY,
    payload bytea NOT NULL,
    revision bigint NOT NULL,
    updated_at timestamptz NOT NULL
)
"""

_UPSERT_SQL = """
INSERT INTO kline_user_archives (username, payload, revision, updated_at)
VALUES (%s, %s, 1, NOW())
ON CONFLICT (username) DO UPDATE SET
    payload = EXCLUDED.payload,
    revision = kline_user_archives.revision + 1,
    updated_at = NOW()
RETURNING revision
"""

_SELECT_USER_SQL = """
SELECT payload, revision
FROM kline_user_archives
WHERE username = %s
"""

_SELECT_ALL_SQL = """
SELECT username, payload
FROM kline_user_archives
ORDER BY username
"""

_DELETE_USER_SQL = """
DELETE FROM kline_user_archives
WHERE username = %s
RETURNING username
"""


class CloudUserArchiveStore:
    """Archive and restore ``users_dir/<username>`` through PostgreSQL."""

    def __init__(
        self,
        users_dir,
        *,
        connection_url: Optional[str] = None,
        environ: Optional[Mapping[str, str]] = None,
        connect: Optional[Callable] = None,
    ):
        environment = os.environ if environ is None else environ
        self.users_dir = Path(users_dir)
        self._connection_url = connection_url or self._select_connection_url(environment)
        self._connect = connect or self._psycopg_connect
        self._schema_ready = False
        self._schema_lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return bool(self._connection_url)

    @staticmethod
    def _select_connection_url(environment: Mapping[str, str]) -> Optional[str]:
        for name in ("POSTGRES_URL", "DATABASE_URL", "DATABASE_URL_UNPOOLED"):
            value = environment.get(name)
            if value and value.strip():
                return value.strip()
        return None

    @staticmethod
    def _psycopg_connect(connection_url):
        try:
            import psycopg
        except ImportError as exc:
            raise CloudStateError(
                "psycopg v3 is required when cloud user archives are enabled"
            ) from exc
        return psycopg.connect(connection_url)

    def _require_enabled(self):
        if not self.enabled:
            raise CloudStateError(
                "cloud user archive store is disabled because no PostgreSQL URL is configured"
            )

    def ensure_schema(self):
        self._require_enabled()
        if self._schema_ready:
            return
        with self._schema_lock:
            if self._schema_ready:
                return
            try:
                with self._connect(self._connection_url) as connection:
                    with connection.cursor() as cursor:
                        cursor.execute(_CREATE_TABLE_SQL)
            except CloudStateError:
                raise
            except Exception as exc:
                raise CloudStateError(
                    f"failed to initialize cloud archive schema: {exc}"
                ) from exc
            self._schema_ready = True

    def save_user(self, username: str) -> int:
        user_path = self._user_path(username)
        if not user_path.is_dir():
            raise FileNotFoundError(f"user directory does not exist: {user_path}")
        if user_path.is_symlink():
            raise CloudStateError(f"cannot archive symbolic link: {user_path}")
        try:
            payload = self._archive_directory(user_path)
        except CloudStateError:
            raise
        except Exception as exc:
            raise CloudStateError(f"failed to archive user '{username}': {exc}") from exc

        self.ensure_schema()
        try:
            with self._connect(self._connection_url) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(_UPSERT_SQL, (username, payload))
                    row = cursor.fetchone()
        except CloudStateError:
            raise
        except Exception as exc:
            raise CloudStateError(
                f"failed to save cloud archive for user '{username}': {exc}"
            ) from exc
        if not row:
            raise CloudStateError(
                f"failed to save cloud archive for user '{username}': revision was not returned"
            )
        return int(row[0])

    def restore_user(self, username: str) -> bool:
        self._user_path(username)
        self.ensure_schema()
        try:
            with self._connect(self._connection_url) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(_SELECT_USER_SQL, (username,))
                    row = cursor.fetchone()
        except CloudStateError:
            raise
        except Exception as exc:
            raise CloudStateError(
                f"failed to load cloud archive for user '{username}': {exc}"
            ) from exc
        if row is None:
            return False
        self._restore_payload(username, bytes(row[0]))
        return True

    def restore_all(self):
        self.ensure_schema()
        try:
            with self._connect(self._connection_url) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(_SELECT_ALL_SQL)
                    rows = cursor.fetchall()
        except CloudStateError:
            raise
        except Exception as exc:
            raise CloudStateError(f"failed to load cloud user archives: {exc}") from exc

        restored = []
        for username, payload in rows:
            self._restore_payload(str(username), bytes(payload))
            restored.append(str(username))
        return restored

    def delete_user(self, username: str) -> bool:
        self._user_path(username)
        self.ensure_schema()
        try:
            with self._connect(self._connection_url) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(_DELETE_USER_SQL, (username,))
                    row = cursor.fetchone()
        except CloudStateError:
            raise
        except Exception as exc:
            raise CloudStateError(
                f"failed to delete cloud archive for user '{username}': {exc}"
            ) from exc
        return row is not None

    def _user_path(self, username: str) -> Path:
        if not isinstance(username, str) or not username:
            raise ValueError("username must be a non-empty string")
        if username in {".", ".."} or "/" in username or "\\" in username:
            raise ValueError("username must identify one direct child of users_dir")
        if "\x00" in username:
            raise ValueError("username contains a null byte")
        return self.users_dir / username

    @staticmethod
    def _archive_directory(user_path: Path) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for root, directory_names, file_names in os.walk(user_path, followlinks=False):
                root_path = Path(root)
                for directory_name in directory_names:
                    directory_path = root_path / directory_name
                    if directory_path.is_symlink():
                        raise CloudStateError(
                            f"cannot archive symbolic link: {directory_path}"
                        )
                if not directory_names and not file_names and root_path != user_path:
                    relative = root_path.relative_to(user_path).as_posix().rstrip("/") + "/"
                    archive.writestr(relative, b"")
                for file_name in file_names:
                    file_path = root_path / file_name
                    if file_path.is_symlink():
                        raise CloudStateError(f"cannot archive symbolic link: {file_path}")
                    archive.write(file_path, file_path.relative_to(user_path).as_posix())
        return buffer.getvalue()

    def _restore_payload(self, username: str, payload: bytes):
        target_path = self._user_path(username)
        self.users_dir.mkdir(parents=True, exist_ok=True)
        temporary_root = Path(
            tempfile.mkdtemp(prefix=f".{username}.restore-", dir=self.users_dir)
        )
        staged_path = temporary_root / "content"
        staged_path.mkdir()
        backup_path = self.users_dir / f".{username}.backup-{uuid.uuid4().hex}"
        moved_existing = False

        try:
            self._extract_archive(payload, staged_path)
            if target_path.exists():
                os.replace(target_path, backup_path)
                moved_existing = True
            try:
                os.replace(staged_path, target_path)
            except Exception:
                if moved_existing and backup_path.exists():
                    os.replace(backup_path, target_path)
                    moved_existing = False
                raise
            if moved_existing and backup_path.exists():
                shutil.rmtree(backup_path)
                moved_existing = False
        except CloudStateError:
            raise
        except Exception as exc:
            raise CloudStateError(f"failed to restore user '{username}': {exc}") from exc
        finally:
            if moved_existing and backup_path.exists() and not target_path.exists():
                try:
                    os.replace(backup_path, target_path)
                except OSError:
                    pass
            shutil.rmtree(temporary_root, ignore_errors=True)

    @classmethod
    def _extract_archive(cls, payload: bytes, destination: Path):
        try:
            with zipfile.ZipFile(io.BytesIO(payload), "r") as archive:
                entries = [(info, cls._safe_archive_path(info)) for info in archive.infolist()]
                for info, relative_path in entries:
                    output_path = destination.joinpath(*relative_path.parts)
                    if info.is_dir():
                        output_path.mkdir(parents=True, exist_ok=True)
                        continue
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    temporary_file = output_path.with_name(
                        f".{output_path.name}.tmp-{uuid.uuid4().hex}"
                    )
                    try:
                        with archive.open(info, "r") as source, temporary_file.open("wb") as output:
                            shutil.copyfileobj(source, output)
                        os.replace(temporary_file, output_path)
                    finally:
                        if temporary_file.exists():
                            temporary_file.unlink()
        except CloudStateError:
            raise
        except (OSError, zipfile.BadZipFile) as exc:
            raise CloudStateError(f"invalid or unreadable user archive: {exc}") from exc

    @staticmethod
    def _safe_archive_path(info: zipfile.ZipInfo) -> PurePosixPath:
        name = info.filename.replace("\\", "/")
        path = PurePosixPath(name)
        mode = info.external_attr >> 16
        unsafe = (
            not name
            or name.startswith("/")
            or path.is_absolute()
            or any(part in {"", ".", ".."} for part in path.parts)
            or (path.parts and ":" in path.parts[0])
            or stat.S_ISLNK(mode)
        )
        if unsafe:
            raise CloudStateError(f"unsafe archive path: {info.filename!r}")
        return path
