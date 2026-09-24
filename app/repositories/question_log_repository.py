from datetime import datetime

from app.models.question_log import QuestionLog
from app.repositories.base import BaseRepository


class QuestionLogRepository(BaseRepository[QuestionLog]):

    model = QuestionLog

    def count_since(self, user_id: int, since: datetime) -> int:
        """Return how many questions a user has been answered since a point in time."""
        return (
            self.db.query(QuestionLog)
            .filter(QuestionLog.user_id == user_id, QuestionLog.created_at >= since)
            .count()
        )

    def log(self, user_id: int) -> QuestionLog:
        """Record one answered question for a user."""
        return self.create(QuestionLog(user_id=user_id))
