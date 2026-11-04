"""RankingStore interface: the cache/ranking abstraction.

Implementations answer top-N, rank, and neighbor queries without being
the source of truth.
"""
from abc import ABC, abstractmethod
from typing import Optional, Sequence, Tuple


class RankingStore(ABC):
    @abstractmethod
    def add(self, game_id: str, season_id: str, user_id: str, score: int, submitted_at: str) -> None:
        """Record a best score for a user in a leaderboard."""
        raise NotImplementedError
        
    @abstractmethod
    def top(self, game_id: str, season_id: str, limit: int) -> Sequence[Tuple[str, int]]:
        """Return up to `limit` (user_id, score) pairs, highest score first."""
        raise NotImplementedError
    
    @abstractmethod
    def rank(self, game_id: str, season_id: str, user_id: str) -> Optional[Tuple[int, int]]:
        """Return (rank, score) for a user, or None if unknown."""
        raise NotImplementedError
    
    @abstractmethod
    def neighbors(self, game_id: str, season_id: str, user_id: str, window: int) -> Sequence[Tuple[str, int, int]]:
        """Return up to `window` players above and below `user_id` as
        (user_id, score, rank), clamped at the board edges."""
        raise NotImplementedError


