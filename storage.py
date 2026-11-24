import hashlib
import json
import uuid
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

import certifi
import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parent
DEFAULT_MEMBERS = ["Haysharya", "Haythuya", "Aung Zaw Latt"]


@contextmanager
def connection(config):
    with TemporaryDirectory() as temp_dir:
        ca_path = certifi.where()
        if config.get("ca_certificate"):
            ca_path = str(Path(temp_dir) / "ca.pem")
            Path(ca_path).write_text(config["ca_certificate"], encoding="utf-8")
        db = psycopg.connect(
            host=config["host"],
            port=int(config.get("port", 5432)),
            user=config["user"],
            password=config["password"],
            dbname=config["database"],
            sslmode="verify-full",
            sslrootcert=ca_path,
            connect_timeout=10,
            row_factory=dict_row,
        )
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()


def verse_key(verse):
    values = [verse["book"], verse["chapter"], verse["verse"], verse["text"]]
    return hashlib.sha256(json.dumps(values, ensure_ascii=False).encode("utf-8")).hexdigest()


def add_verse(cursor, table, verse):
    if table not in ("prayer_custom_verses", "prayer_favorites"):
        raise ValueError("Invalid verse table")
    cursor.execute(
        f"INSERT INTO {table} (verse_key, book, chapter, verse, text) "
        "VALUES (%s, %s, %s, %s, %s) ON CONFLICT (verse_key) DO NOTHING",
        (verse_key(verse), verse["book"], verse["chapter"], verse["verse"], verse["text"]),
    )


def initialize(config):
    with connection(config) as db:
        with db.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s, %s)", (1347569234, 1))
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS prayer_migrations "
                "(name VARCHAR(100) PRIMARY KEY)"
            )
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS prayer_members "
                "(name VARCHAR(190) PRIMARY KEY)"
            )
            for table in ("prayer_custom_verses", "prayer_favorites"):
                cursor.execute(
                    f"CREATE TABLE IF NOT EXISTS {table} ("
                    "verse_key CHAR(64) PRIMARY KEY, book VARCHAR(190) NOT NULL, "
                    "chapter INT NOT NULL, verse INT NOT NULL, text TEXT NOT NULL"
                    ")"
                )
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS prayer_worship_sessions ("
                "id UUID PRIMARY KEY, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), "
                "verse JSONB NOT NULL, leader VARCHAR(190) NOT NULL, teacher VARCHAR(190) NOT NULL, "
                "teaching JSONB NOT NULL, prayer_audio_file_id TEXT, teaching_audio_file_id TEXT)"
            )
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS prayer_app_settings "
                "(key VARCHAR(100) PRIMARY KEY, value TEXT NOT NULL)"
            )
            cursor.execute("INSERT INTO prayer_migrations (name) VALUES (%s) ON CONFLICT DO NOTHING", ("legacy-v1",))
            if cursor.rowcount:
                family_file = ROOT / "family.json"
                members = json.loads(family_file.read_text(encoding="utf-8")) if family_file.exists() else DEFAULT_MEMBERS
                cursor.executemany("INSERT INTO prayer_members (name) VALUES (%s) ON CONFLICT DO NOTHING", [(name,) for name in members])
                bible_file = ROOT / "bible.json"
                if bible_file.exists():
                    for verse in json.loads(bible_file.read_text(encoding="utf-8")):
                        add_verse(cursor, "prayer_custom_verses", verse)


def list_members(config):
    with connection(config) as db:
        with db.cursor() as cursor:
            cursor.execute("SELECT name FROM prayer_members ORDER BY name")
            return [row["name"] for row in cursor.fetchall()]


def save_member(config, name):
    with connection(config) as db:
        with db.cursor() as cursor:
            cursor.execute(
                "INSERT INTO prayer_members (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
                (name,),
            )
            return bool(cursor.rowcount)


def list_verses(config, table):
    if table not in ("prayer_custom_verses", "prayer_favorites"):
        raise ValueError("Invalid verse table")
    with connection(config) as db:
        with db.cursor() as cursor:
            cursor.execute(f"SELECT book, chapter, verse, text FROM {table} ORDER BY book, chapter, verse")
            return cursor.fetchall()


def save_verse(config, table, verse):
    with connection(config) as db:
        with db.cursor() as cursor:
            add_verse(cursor, table, verse)
            return bool(cursor.rowcount)


def save_worship_session(config, verse, leader, teacher, teaching):
    session_id = uuid.uuid4()
    with connection(config) as db:
        with db.cursor() as cursor:
            cursor.execute(
                "INSERT INTO prayer_worship_sessions (id, verse, leader, teacher, teaching) "
                "VALUES (%s, %s::jsonb, %s, %s, %s::jsonb)",
                (session_id, json.dumps(verse, ensure_ascii=False), leader, teacher, json.dumps(teaching, ensure_ascii=False)),
            )
    return str(session_id)


def list_worship_sessions(config, limit=20, offset=0):
    if not 1 <= limit <= 100 or offset < 0:
        raise ValueError("Invalid history limit")
    with connection(config) as db:
        with db.cursor() as cursor:
            cursor.execute(
                "SELECT id, created_at, verse, leader, teacher, teaching, "
                "prayer_audio_file_id, teaching_audio_file_id "
                "FROM prayer_worship_sessions ORDER BY created_at DESC, id DESC LIMIT %s OFFSET %s",
                (limit, offset),
            )
            return cursor.fetchall()


def count_worship_sessions(config):
    with connection(config) as db:
        with db.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS total FROM prayer_worship_sessions")
            return cursor.fetchone()["total"]


def save_session_audio(config, session_id, role, file_id):
    column = {
        "prayer": "prayer_audio_file_id",
        "teaching": "teaching_audio_file_id",
    }.get(role)
    if column is None:
        raise ValueError("Invalid audio role")
    with connection(config) as db:
        with db.cursor() as cursor:
            cursor.execute(
                f"UPDATE prayer_worship_sessions SET {column} = %s WHERE id = %s",
                (file_id, session_id),
            )
            return cursor.rowcount == 1
