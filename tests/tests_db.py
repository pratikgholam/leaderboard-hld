"""Integration tests for store/db.py against a real PostgreSQL."""
import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from leaderboard_hld.store.db import Base, init_db, record_score, BestScore

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://leaderboard:leaderboard@localhost:5432/leaderboard",
)

@pytest.fixture(scope="module")
def engine():
    eng = create_engine(DATABASE_URL)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    
@pytest.fixture
def session(engine):
    connection = engine.connect()
    transaction = connection.begin()
    sess = sessionmaker(bind=connection)()
    yield sess
    sess.close()
    transaction.rollback()
    connection.close()
    
def test_best_score_rule(session):
    record_score(session, "g1", None, "alice", 100, "2026-01-01T10:00:00+00:00")
    record_score(session, "g1", None, "alice", 80, "2026-01-01T11:00:00+00:00")
    best = (
        session.query(BestScore)
        .filter_by(game_id="g1", season_id=None, user_id="alice")
        .one()
    )
    assert best.score == 100