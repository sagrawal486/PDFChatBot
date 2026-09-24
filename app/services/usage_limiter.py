"""Per-user rate limiting for costed operations such as answering questions."""

from datetime import datetime, timedelta
from typing import Callable, Protocol


class UsageLimitExceeded(Exception):
    """Raised when a user has exceeded their allowed usage for the window."""


class UsageLogRepository(Protocol):
    """Persistence boundary required to count and record usage events."""

    def count_since(self, user_id: int, since: datetime) -> int:
        """Return how many events a user has logged since a point in time."""

    def log(self, user_id: int) -> object:
        """Record one usage event for a user."""


class DailyQuestionLimiter:
    """Bound how many questions one user can have answered in a rolling 24h window."""

    def __init__(
        self,
        repository: UsageLogRepository,
        max_per_day: int,
        clock: Callable[[], datetime] = datetime.utcnow,
    ) -> None:
        """Inject the usage log repository and configure the daily bound."""
        if max_per_day <= 0:
            raise ValueError("max_per_day must be greater than zero")
        self.repository = repository
        self.max_per_day = max_per_day
        self.clock = clock

    def ensure_within_limit(self, user_id: int) -> None:
        """Raise UsageLimitExceeded if the user has already reached today's bound."""
        since = self.clock() - timedelta(days=1)
        if self.repository.count_since(user_id, since) >= self.max_per_day:
            raise UsageLimitExceeded(
                f"Daily question limit of {self.max_per_day} reached. Try again later."
            )

    def record(self, user_id: int) -> None:
        """Record that a question was answered for the user."""
        self.repository.log(user_id)
