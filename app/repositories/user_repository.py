from sqlalchemy import select
from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):

    model = User

    def get_by_email(self, email: str):
        statement = select(User).where(
            User.email == email
        )
        return self.db.scalar(statement)

    def get_by_id(self, user_id: int):
        return self.db.get(User, user_id)
