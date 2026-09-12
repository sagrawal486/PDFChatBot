from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.settings import settings
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.user import User

# Import all models before creating sessions so SQLAlchemy can resolve
# relationships and foreign keys in every process, including Celery workers.

# DATABASE_URL = (
#     f"postgresql://{settings.DB_USER}:"
#     f"{settings.DB_PASSWORD}@"
#     f"{settings.DB_HOST}:"
#     f"{settings.DB_PORT}/"
#     f"{settings.DB_NAME}"
# )

engine = create_engine(
    settings.database_url,
    echo=settings.DEBUG
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)
