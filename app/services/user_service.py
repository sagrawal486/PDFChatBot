from fastapi import HTTPException, status

from app.core.jwt import create_access_token
from app.core.security import (
    hash_password,
    verify_password,
)
from app.repositories.user_repository import UserRepository
from app.schemas.auth import RegisterRequest


class UserService:

    def __init__(self,repository: UserRepository,):
        self.repository = repository

    def register(
        self,
        request: RegisterRequest,
    ):

        existing_user = self.repository.get_by_email(
            request.email
        )

        if existing_user:

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )

        user = self.repository.create(
            self.repository.model(
                name=request.name,
                email=request.email,
                password_hash=hash_password(
                    request.password
                ),
            )
        )

        return user

    def login(
        self,
        email: str,
        password: str,
    ):

        user = self.repository.get_by_email(email)

        if not user or not verify_password(
            password,
            user.password_hash,
        ):

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
                headers={
                    "WWW-Authenticate": "Bearer"
                },
            )

        return create_access_token(user.id)
