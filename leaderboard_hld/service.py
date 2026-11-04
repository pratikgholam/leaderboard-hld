"""LeaderboardService: business rules that coordinate storage.

Enforces the best-score rule and tie-break (earliest submitted_at wins),
then updates the store. Knows nothing about Redis or SQL.
"""
from typing import Optional, Sequence, Tuple
from leaderboard_hld.store.base import RankingStore


class LeaderboardService:
    def __init__(self, store: RankingStore) -> None:
        self._store = store
        # best_scores[(game_id, season_id, user_id)] = (score, submitted_at)
        self._best_scores: dict[tuple[str, str, str], tuple[int, str]] = {}
        
    def submit_score(self, game_id: str, season_id: Optional[str], user_id: str, score: int, submitted_at: str) -> None:
        if score < 0:
            raise ValueError("Score must not be negative")
        season = season_id or "all"
        key = (game_id, season, user_id)
        current = self._best_scores.get(key)
        if current is None:
            self._best_scores[key] = (score, submitted_at)
            self._store.add(game_id, season, user_id, score, submitted_at)
        else:
            best_score, best_at = current
            if score > best_score:
                self._best_scores[key] = (score, submitted_at)
                self._store.add(game_id, season, user_id, score, submitted_at)
            elif score == best_score and submitted_at < best_at:
                # Tie: earlier achievement ranks higher
                self._best_scores[key] = (score, submitted_at)
                self._store.add(game_id, season, user_id, score, submitted_at)
                
    def get_leaderboard(self, game_id: str, season_id: Optional[str], limit: int) -> Sequence[Tuple[str, int]]:
        season = season_id or "all"
        return self._store.top(game_id, season, limit)
    
    def get_rank(self, game_id: str, season_id: Optional[str], user_id: str) -> Optional[Tuple[int, int]]:
        season = season_id or "all"
        return self._store.rank(game_id, season, user_id)
    
    def get_neighbors(self, game_id: str, season_id: Optional[str], user_id: str, window: int,) -> Sequence[Tuple[str, int, int]]:
        season = season_id or "all"
        return self._store.neighbors(game_id, season, user_id, window)