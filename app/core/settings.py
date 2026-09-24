from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME: str = "AI PDF Chatbot"
    DEBUG: bool = False

    DB_HOST: str
    DB_PORT: int = 5432
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str

    CHAT_PROVIDER: str = "simple"  # "simple" (free, returns context) or "bedrock"
    CHAT_MODEL_ID: str = "apac.amazon.nova-micro-v1:0"
    CHAT_MAX_TOKENS: int = 512
    CORS_ORIGINS: str = "http://localhost:3000"
    EMBEDDING_MODEL_ID: str = "amazon.titan-embed-text-v2:0"

    STORAGE_BACKEND: str = "local"
    S3_BUCKET: str = ""
    AWS_REGION: str = "ap-south-1"

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    MAX_UPLOAD_SIZE_MB: int = 10
    PGVECTOR_DIMENSION: int = 1024
    PGVECTOR_ENABLED: bool = True

    # Cost/abuse bounds: cap chunks embedded per document and questions answered per user.
    MAX_CHUNKS_PER_DOCUMENT: int = 500
    EMBEDDING_CONCURRENCY: int = 5
    MAX_QUESTIONS_PER_DAY: int = 30

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.DB_USER}:"
            f"{self.DB_PASSWORD}@"
            f"{self.DB_HOST}:"
            f"{self.DB_PORT}/"
            f"{self.DB_NAME}"
        )

    @property
    def cors_origins_list(self) -> list[str]:
        """Return configured CORS origins as a list."""
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def redis_url(self) -> str:
        """Return the Redis URL used by Celery."""
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"


@lru_cache
def get_settings():
    return Settings()


settings = get_settings()
