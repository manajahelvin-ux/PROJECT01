"""Phase 11 - persistance SQLite via SQLAlchemy : historique des transcriptions."""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from sqlalchemy import Integer, String, Text, create_engine, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from transcribe_ai.config.settings import get_settings
from transcribe_ai.core.exceptions import StorageError
from transcribe_ai.core.models import JobStatus, TranscriptionJob
from transcribe_ai.utils.logging_config import get_logger
from transcribe_ai.utils.text import word_count

logger = get_logger(__name__)


class Base(DeclarativeBase):
    pass


class TranscriptionRecord(Base):
    """Une ligne d'historique."""

    __tablename__ = "transcriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500), default="")
    url: Mapped[str] = mapped_column(String(2000), default="")
    duration: Mapped[float] = mapped_column(default=0.0)
    language: Mapped[str] = mapped_column(String(16), default="auto")
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default=JobStatus.COMPLETED.value)
    transcription_path: Mapped[str] = mapped_column(String(1000), default="")
    audio_path: Mapped[str] = mapped_column(String(1000), default="")

    # Champs complementaires, utiles a la reouverture d'une transcription.
    author: Mapped[str] = mapped_column(String(300), default="")
    source_type: Mapped[str] = mapped_column(String(32), default="url")
    text: Mapped[str] = mapped_column(Text, default="")
    ai_summary: Mapped[str] = mapped_column(Text, default="")
    ai_key_points: Mapped[str] = mapped_column(Text, default="")   # JSON
    segments_json: Mapped[str] = mapped_column(Text, default="")   # JSON
    ai_calls: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")

    def key_points(self) -> list[str]:
        try:
            return json.loads(self.ai_key_points or "[]")
        except json.JSONDecodeError:
            return []

    def segments(self) -> list[dict]:
        try:
            return json.loads(self.segments_json or "[]")
        except json.JSONDecodeError:
            return []

    def __repr__(self) -> str:  # pragma: no cover - confort de debogage
        return f"<TranscriptionRecord {self.id} {self.title[:30]!r}>"


class Database:
    """Encapsule le moteur SQLAlchemy et la fabrique de sessions."""

    def __init__(self, url: str | None = None) -> None:
        self.url = url or get_settings().resolved_database_url
        self.engine = create_engine(self.url, echo=False, future=True)
        self._session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        Base.metadata.create_all(self.engine)
        logger.debug("Base de donnees prete : %s", self.url)

    @contextmanager
    def session(self) -> Iterator[Session]:
        """Session transactionnelle : commit automatique, rollback sur erreur."""
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except SQLAlchemyError as exc:
            session.rollback()
            logger.error("Erreur SQL : %s", exc)
            raise StorageError(str(exc)) from exc
        finally:
            session.close()

    def dispose(self) -> None:
        self.engine.dispose()


class HistoryRepository:
    """Operations metier sur l'historique (creation, lecture, mise a jour...)."""

    def __init__(self, database: Database | None = None) -> None:
        self.db = database or Database()

    # -- ecriture --------------------------------------------------------
    def add(self, record: TranscriptionRecord) -> TranscriptionRecord:
        with self.db.session() as session:
            session.add(record)
            session.flush()
            session.refresh(record)
            return record

    def save_job(self, job: TranscriptionJob, text: str | None = None) -> TranscriptionRecord:
        """Enregistre (ou met a jour) un job termine."""
        info = job.media_info
        ai = job.ai_result
        content = text if text is not None else (
            (ai.cleaned_text if ai and ai.cleaned_text else "")
            or (job.transcription.text if job.transcription else "")
        )
        segments = (
            [
                {"index": s.index, "start": s.start, "end": s.end, "text": s.text}
                for s in job.transcription.segments
            ]
            if job.transcription
            else []
        )
        record = TranscriptionRecord(
            title=job.title,
            url=job.source,
            duration=(info.duration if info else 0.0),
            language=(job.transcription.language if job.transcription else job.language),
            created_at=datetime.now(),
            word_count=word_count(content),
            status=job.status.value,
            transcription_path="",
            audio_path=str(job.audio_path or ""),
            author=(info.author if info and info.author else ""),
            source_type=job.source_type.value,
            text=content,
            ai_summary=(ai.short_summary if ai else ""),
            ai_key_points=json.dumps(ai.key_points if ai else [], ensure_ascii=False),
            segments_json=json.dumps(segments, ensure_ascii=False),
            ai_calls=(ai.usage.calls if ai else 0),
            error=job.error or "",
        )
        if job.record_id:
            record.id = job.record_id
            return self.update(record)
        saved = self.add(record)
        job.record_id = saved.id
        return saved

    def update(self, record: TranscriptionRecord) -> TranscriptionRecord:
        with self.db.session() as session:
            merged = session.merge(record)
            session.flush()
            return merged

    def update_text(self, record_id: int, text: str) -> None:
        """Sauvegarde les corrections faites dans l'editeur."""
        with self.db.session() as session:
            record = session.get(TranscriptionRecord, record_id)
            if record is None:
                raise StorageError(
                    f"Enregistrement {record_id} introuvable",
                    user_message="Cette transcription n'existe plus dans l'historique.",
                )
            record.text = text
            record.word_count = word_count(text)

    def set_transcription_path(self, record_id: int, path: str | Path) -> None:
        with self.db.session() as session:
            record = session.get(TranscriptionRecord, record_id)
            if record is not None:
                record.transcription_path = str(path)

    # -- lecture ---------------------------------------------------------
    def get(self, record_id: int) -> TranscriptionRecord | None:
        with self.db.session() as session:
            return session.get(TranscriptionRecord, record_id)

    def list(self, limit: int = 200, search: str = "") -> list[TranscriptionRecord]:
        with self.db.session() as session:
            query = select(TranscriptionRecord)
            if search.strip():
                pattern = f"%{search.strip()}%"
                query = query.where(
                    TranscriptionRecord.title.ilike(pattern)
                    | TranscriptionRecord.url.ilike(pattern)
                    | TranscriptionRecord.text.ilike(pattern)
                )
            query = query.order_by(TranscriptionRecord.created_at.desc()).limit(limit)
            return list(session.scalars(query))

    def count(self) -> int:
        with self.db.session() as session:
            return int(session.scalar(select(func.count(TranscriptionRecord.id))) or 0)

    def stats(self) -> dict[str, float | int]:
        """Chiffres affiches sur la page d'accueil."""
        with self.db.session() as session:
            return {
                "count": int(session.scalar(select(func.count(TranscriptionRecord.id))) or 0),
                "words": int(session.scalar(select(func.sum(TranscriptionRecord.word_count))) or 0),
                "duration": float(
                    session.scalar(select(func.sum(TranscriptionRecord.duration))) or 0.0
                ),
                "ai_calls": int(
                    session.scalar(select(func.sum(TranscriptionRecord.ai_calls))) or 0
                ),
            }

    # -- suppression -----------------------------------------------------
    def delete(self, record_id: int) -> bool:
        with self.db.session() as session:
            record = session.get(TranscriptionRecord, record_id)
            if record is None:
                return False
            session.delete(record)
            return True

    def clear(self) -> int:
        with self.db.session() as session:
            records = list(session.scalars(select(TranscriptionRecord)))
            for record in records:
                session.delete(record)
            return len(records)
