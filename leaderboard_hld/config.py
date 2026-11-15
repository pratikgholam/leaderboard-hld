"""Settings from environment variables. No hardcoded hosts, ports, or passwords."""
import os

def get_env(name: str,default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value

DATABASE_URL = get_env("DATABASE_URL","postgresql+psycopg2://leaderboard:leaderboard@localhost:5432/leaderboard")
REDIS_URL = get_env("REDIS_URL","redis://localhost:6379/0")