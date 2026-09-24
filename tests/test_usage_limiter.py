"""Tests for the rolling-window daily question limiter."""

from datetime import datetime, timedelta

import pytest

from app.services.usage_limiter import DailyQuestionLimiter, UsageLimitExceeded


class FakeUsageLogRepository:
    """Fake usage log repository with a controllable count."""

    def __init__(self, count: int = 0) -> None:
        self.count = count
        self.counted_users: list[int] = []
        self.count_since_args: list[tuple[int, datetime]] = []
        self.logged_users: list[int] = []

    def count_since(self, user_id: int, since: datetime) -> int:
        self.counted_users.append(user_id)
        self.count_since_args.append((user_id, since))
        return self.count

    def log(self, user_id: int) -> None:
        self.logged_users.append(user_id)


def test_limiter_allows_requests_under_the_daily_bound() -> None:
    repository = FakeUsageLogRepository(count=5)
    limiter = DailyQuestionLimiter(repository, max_per_day=30)

    limiter.ensure_within_limit(user_id=7)  # does not raise

    assert repository.counted_users == [7]


def test_limiter_rejects_requests_at_the_daily_bound() -> None:
    repository = FakeUsageLogRepository(count=30)
    limiter = DailyQuestionLimiter(repository, max_per_day=30)

    with pytest.raises(UsageLimitExceeded):
        limiter.ensure_within_limit(user_id=7)


def test_limiter_counts_a_rolling_24_hour_window() -> None:
    repository = FakeUsageLogRepository(count=0)
    fixed_now = datetime(2026, 1, 2, 12, 0, 0)
    limiter = DailyQuestionLimiter(repository, max_per_day=30, clock=lambda: fixed_now)

    limiter.ensure_within_limit(user_id=7)

    assert repository.count_since_args == [(7, fixed_now - timedelta(days=1))]


def test_limiter_records_usage() -> None:
    repository = FakeUsageLogRepository()
    limiter = DailyQuestionLimiter(repository, max_per_day=30)

    limiter.record(user_id=7)

    assert repository.logged_users == [7]


def test_limiter_rejects_invalid_configuration() -> None:
    with pytest.raises(ValueError, match="max_per_day"):
        DailyQuestionLimiter(FakeUsageLogRepository(), max_per_day=0)
