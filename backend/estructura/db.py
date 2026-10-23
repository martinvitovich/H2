"""Base de datos SQLite del proyecto con integridad referencial y migraciones versionadas.

Cada migración es una lista de sentencias SQL que lleva el esquema de la versión ``n-1`` a la
``n``; la versión aplicada se guarda en ``meta.schema_version``. Las migraciones no borran datos.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

DB_FILENAME = "ha_anejo19.sqlite3"

MIGRATIONS: list[list[str]] = [
    # 1: esquema inicial
    [
        """CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)""",
        """CREATE TABLE projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            location TEXT NOT NULL DEFAULT '',
            client TEXT NOT NULL DEFAULT '',
            project_date TEXT NOT NULL DEFAULT '',
            structural_system TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'activo' CHECK (status IN ('activo', 'archivado')),
            norm_json TEXT NOT NULL,
            settings_json TEXT NOT NULL DEFAULT '{}',
            parameter_overrides_json TEXT NOT NULL DEFAULT '{}',
            software_version TEXT NOT NULL,
            created TEXT NOT NULL,
            modified TEXT NOT NULL,
            rev INTEGER NOT NULL DEFAULT 1
        )""",
        """CREATE TABLE levels (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            code TEXT NOT NULL,
            name TEXT NOT NULL DEFAULT '',
            elevation_m REAL,
            height_m REAL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            UNIQUE (project_id, code)
        )""",
        """CREATE TABLE elements (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            level_id TEXT REFERENCES levels(id) ON DELETE RESTRICT,
            type TEXT NOT NULL CHECK (type IN ('losa', 'viga', 'pilar', 'zapata')),
            code TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            data_json TEXT NOT NULL DEFAULT '{}',
            created TEXT NOT NULL,
            modified TEXT NOT NULL,
            UNIQUE (project_id, code)
        )""",
        """CREATE INDEX idx_elements_project ON elements(project_id, type)""",
        """CREATE TABLE links (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            source_id TEXT NOT NULL REFERENCES elements(id) ON DELETE CASCADE,
            target_id TEXT NOT NULL REFERENCES elements(id) ON DELETE CASCADE,
            kind TEXT NOT NULL CHECK (kind IN ('losa_viga', 'viga_apoyo', 'pilar_pilar', 'pilar_zapata')),
            data_json TEXT NOT NULL DEFAULT '{}',
            created TEXT NOT NULL,
            UNIQUE (source_id, target_id, kind),
            CHECK (source_id <> target_id)
        )""",
        """CREATE INDEX idx_links_target ON links(target_id)""",
        """CREATE INDEX idx_links_source ON links(source_id)""",
        # Las relaciones no pueden cruzar proyectos
        """CREATE TRIGGER links_same_project BEFORE INSERT ON links
           WHEN (SELECT project_id FROM elements WHERE id = NEW.source_id) <> NEW.project_id
             OR (SELECT project_id FROM elements WHERE id = NEW.target_id) <> NEW.project_id
           BEGIN SELECT RAISE(ABORT, 'La relación une elementos de proyectos distintos'); END""",
        """CREATE TRIGGER elements_level_same_project BEFORE INSERT ON elements
           WHEN NEW.level_id IS NOT NULL
             AND (SELECT project_id FROM levels WHERE id = NEW.level_id) <> NEW.project_id
           BEGIN SELECT RAISE(ABORT, 'El nivel pertenece a otro proyecto'); END""",
        """CREATE TRIGGER elements_level_same_project_u BEFORE UPDATE OF level_id ON elements
           WHEN NEW.level_id IS NOT NULL
             AND (SELECT project_id FROM levels WHERE id = NEW.level_id) <> NEW.project_id
           BEGIN SELECT RAISE(ABORT, 'El nivel pertenece a otro proyecto'); END""",
        """CREATE TABLE results (
            id TEXT PRIMARY KEY,
            element_id TEXT NOT NULL REFERENCES elements(id) ON DELETE CASCADE,
            calc_type TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('ok', 'error')),
            computed_at TEXT NOT NULL,
            engine_version TEXT NOT NULL,
            input_hash TEXT NOT NULL,
            input_json TEXT NOT NULL,
            output_json TEXT,
            error TEXT,
            UNIQUE (element_id, calc_type)
        )""",
        """CREATE TABLE history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            element_id TEXT,
            element_code TEXT,
            ts TEXT NOT NULL,
            action TEXT NOT NULL,
            detail_json TEXT NOT NULL DEFAULT '{}'
        )""",
        """CREATE INDEX idx_history_project ON history(project_id, ts)""",
        # Cálculos independientes (formato de proyecto 1: documentos de las calculadoras)
        """CREATE TABLE calc_documents (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            sort_order INTEGER NOT NULL DEFAULT 0,
            type TEXT NOT NULL,
            name TEXT NOT NULL DEFAULT '',
            input_json TEXT NOT NULL,
            result_json TEXT
        )""",
        # Ficheros JSON del almacenamiento anterior ya importados (los ficheros no se borran)
        """CREATE TABLE legacy_imports (
            filename TEXT PRIMARY KEY,
            project_id TEXT,
            imported_at TEXT NOT NULL,
            note TEXT NOT NULL DEFAULT ''
        )""",
    ],
]

SCHEMA_VERSION = len(MIGRATIONS)


class Database:
    """Conexión SQLite compartida (un único proceso; acceso serializado con un cerrojo)."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        if str(path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        if str(path) != ":memory:":
            self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.execute("PRAGMA synchronous = FULL")
        self.migrate()

    def schema_version(self) -> int:
        cur = self.conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='meta'")
        if cur.fetchone() is None:
            return 0
        row = self.conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        return int(row["value"]) if row else 0

    def migrate(self) -> None:
        with self.lock:
            v = self.schema_version()
            if v > SCHEMA_VERSION:
                raise RuntimeError(f"La base de datos usa el esquema {v}, más reciente que el soportado "
                                   f"({SCHEMA_VERSION}). Actualice la aplicación.")
            for n in range(v, SCHEMA_VERSION):
                self.conn.execute("BEGIN")
                try:
                    for sql in MIGRATIONS[n]:
                        self.conn.execute(sql)
                    self.conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', ?)",
                                      (str(n + 1),))
                    self.conn.execute("COMMIT")
                except Exception:
                    self.conn.execute("ROLLBACK")
                    raise

    def tx(self) -> "_Tx":
        return _Tx(self)

    def close(self) -> None:
        self.conn.close()


class _Tx:
    """Transacción explícita: ``with db.tx() as c: ...`` (COMMIT o ROLLBACK)."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def __enter__(self) -> sqlite3.Connection:
        self.db.lock.acquire()
        self.db.conn.execute("BEGIN IMMEDIATE")
        return self.db.conn

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            self.db.conn.execute("ROLLBACK" if exc_type else "COMMIT")
        finally:
            self.db.lock.release()
