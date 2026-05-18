import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.models import SpeakerVoiceProfile


class VoiceProfileStore:
    def __init__(self, database_path: Path):
        self.database_path = database_path
        self._init_db()

    def list_profiles(self) -> list[SpeakerVoiceProfile]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, voice_id, voice_name, provider, description,
                       consent_confirmed, created_at, last_used_at
                FROM voice_profiles
                ORDER BY datetime(created_at) DESC
                """
            ).fetchall()
        return [self._row_to_profile(row) for row in rows]

    def upsert_profile(
        self,
        voice_id: str,
        voice_name: str,
        provider: str,
        consent_confirmed: bool,
        description: str | None = None,
    ) -> SpeakerVoiceProfile:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO voice_profiles (
                    voice_id, voice_name, provider, description,
                    consent_confirmed, created_at, last_used_at
                )
                VALUES (?, ?, ?, ?, ?, ?, NULL)
                ON CONFLICT(voice_id) DO UPDATE SET
                    voice_name = excluded.voice_name,
                    provider = excluded.provider,
                    description = excluded.description,
                    consent_confirmed = excluded.consent_confirmed
                """,
                (voice_id, voice_name, provider, description, int(consent_confirmed), now),
            )
            row = conn.execute(
                """
                SELECT id, voice_id, voice_name, provider, description,
                       consent_confirmed, created_at, last_used_at
                FROM voice_profiles
                WHERE voice_id = ?
                """,
                (voice_id,),
            ).fetchone()
        return self._row_to_profile(row)

    def mark_used(self, voice_id: str) -> None:
        if not voice_id:
            return
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                "UPDATE voice_profiles SET last_used_at = ? WHERE voice_id = ?",
                (now, voice_id),
            )

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS voice_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    voice_id TEXT NOT NULL UNIQUE,
                    voice_name TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    description TEXT,
                    consent_confirmed INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    last_used_at TEXT
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _row_to_profile(row: sqlite3.Row) -> SpeakerVoiceProfile:
        return SpeakerVoiceProfile(
            id=row["id"],
            voice_id=row["voice_id"],
            voice_name=row["voice_name"],
            provider=row["provider"],
            description=row["description"],
            consent_confirmed=bool(row["consent_confirmed"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            last_used_at=datetime.fromisoformat(row["last_used_at"]) if row["last_used_at"] else None,
        )
