"""PostgreSQL access: scores and best_scores tables. Durable source of truth."""
from typing import Optional
from sqlalchemy import BigInteger, Column, DateTime, Index, Text, create_engine, func
from sqlalchemy.orm import declarative_base, sessionmaker, Session

Base = declarative_base()

class Score(Base):
    __tablename__ = "scores"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    game_id = Column(Text, nullable=False, index=True)
    season_id = Column(Text, nullable=True, index=True)
    user_id = Column(Text, nullable=False)
    score = Column(BigInteger, nullable=False)
    submitted_at = Column(DateTime(timezone=True), nullable=False)
    
    
class BestScore(Base):
    __tablename__ = "best_scores"
    game_id = Column(Text, primary_key=True)
    season_id = Column(Text, primary_key=True)
    user_id = Column(Text, primary_key=True)
    score = Column(BigInteger, nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_best_scores_game_season_score", "game_id", "season_id", "score"),
    )
    
    def init_db(database_url: str) -> None:
        """Create engine and session factory. Call once at app startup."""
        global _engine, _SessionLocal
        _engine = create_engine(database_url, pool_pre_ping=True)
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)


    def session() -> Session:
        return _SessionLocal()
    
    def record_score(
    session: Session,
    game_id: str,
    season_id: Optional[str],
    user_id: str,
    score: int,
    submitted_at,
) -> bool:
        """Insert a raw score row and upsert best_scores.

        Returns True when the user's best score actually changed (inserted or
        improved). Equal scores keep the earliest submitted_at (no update).
        """
        session.add(
            Score(
                game_id=game_id,
                season_id=season_id,
                user_id=user_id,
                score=score,
                submitted_at=submitted_at,
            )
        )

        best = (
            session.query(BestScore)
            .filter_by(game_id=game_id, season_id=season_id, user_id=user_id)
            .one_or_none()
        )

        changed = False
        if best is None:
            session.add(
                BestScore(
                    game_id=game_id,
                    season_id=season_id,
                    user_id=user_id,
                    score=score,
                    updated_at=submitted_at,
                )
            )
            changed = True
        elif score > best.score:
            best.score = score
            best.updated_at = submitted_at
            changed = True
        # score == best.score: keep earliest submitted_at — do nothing

        session.commit()
        return changed