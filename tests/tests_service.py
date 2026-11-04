"""Unit tests for LeaderboardService using an in-memory fake RankingStore."""

from leaderboard_hld.service import LeaderboardService
from leaderboard_hld.store.base import RankingStore


class FakeRankingStore(RankingStore):
    def __init__(self) -> None:
        self._entries: dict[tuple[str, str, str], tuple[int, str]] = {}

    def add(self, game_id, season_id, user_id, score, submitted_at):
        key = (game_id, season_id, user_id)
        cur = self._entries.get(key)
        if cur is None or score > cur[0] or (score == cur[0] and submitted_at < cur[1]):
            self._entries[key] = (score, submitted_at)

    def _sorted(self, game_id, season_id):
        items = [
            (uid, score, at)
            for (g, s, uid), (score, at) in self._entries.items()
            if g == game_id and s == season_id
        ]
        items.sort(key=lambda x: (-x[1], x[2]))
        return items

    def top(self, game_id, season_id, limit):
        return [(uid, score) for uid, score, _ in self._sorted(game_id, season_id)[:limit]]

    def rank(self, game_id, season_id, user_id):
        for i, (uid, score, _) in enumerate(self._sorted(game_id, season_id), start=1):
            if uid == user_id:
                return (i, score)
        return None

    def neighbors(self, game_id, season_id, user_id, window):
        ordered = self._sorted(game_id, season_id)
        idx = next((i for i, (uid, _, _) in enumerate(ordered) if uid == user_id), None)
        if idx is None:
            return []
        start = max(0, idx - window)
        end = min(len(ordered), idx + window + 1)
        return [(uid, score, i + 1) for i, (uid, score, _) in enumerate(ordered[start:end], start=start)]


def make_service() -> LeaderboardService:
    return LeaderboardService(FakeRankingStore())


def test_lower_score_does_not_lower_rank():
    svc = make_service()
    svc.submit_score("g1", None, "alice", 100, "2026-01-01T10:00:00Z")
    svc.submit_score("g1", None, "bob", 90, "2026-01-01T10:00:00Z")
    svc.submit_score("g1", None, "alice", 80, "2026-01-01T11:00:00Z")  # lower, ignored
    assert svc.get_rank("g1", None, "alice") == (1, 100)
    assert svc.get_leaderboard("g1", None, 10) == [("alice", 100), ("bob", 90)]


def test_tie_break_earliest_wins():
    svc = make_service()
    svc.submit_score("g1", None, "alice", 100, "2026-01-01T10:00:00Z")
    svc.submit_score("g1", None, "bob", 100, "2026-01-01T11:00:00Z")
    assert svc.get_leaderboard("g1", None, 10) == [("alice", 100), ("bob", 100)]
    assert svc.get_rank("g1", None, "alice") == (1, 100)
    assert svc.get_rank("g1", None, "bob") == (2, 100)


def test_top_n_returns_correct_order_and_length():
    svc = make_service()
    for i, (user, score) in enumerate([("a", 300), ("b", 200), ("c", 100), ("d", 50)]):
        svc.submit_score("g1", None, user, score, f"2026-01-01T10:00:{i:02d}Z")
    top = svc.get_leaderboard("g1", None, 2)
    assert top == [("a", 300), ("b", 200)]
    assert len(top) == 2


def test_neighbors_clamp_at_edges():
    svc = make_service()
    for i, (user, score) in enumerate([("a", 300), ("b", 200), ("c", 100)]):
        svc.submit_score("g1", None, user, score, f"2026-01-01T10:00:{i:02d}Z")
    # top of board: fewer rows above
    assert svc.get_neighbors("g1", None, "a", 5) == [("a", 300, 1), ("b", 200, 2), ("c", 100, 3)]
    # bottom of board: fewer rows below
    assert svc.get_neighbors("g1", None, "c", 5) == [("a", 300, 1), ("b", 200, 2), ("c", 100, 3)]


def test_unknown_user_returns_none():
    svc = make_service()
    assert svc.get_rank("g1", None, "nobody") is None