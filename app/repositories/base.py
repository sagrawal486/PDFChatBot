from typing import Generic, TypeVar
from sqlalchemy.orm import Session

ModelType = TypeVar("ModelType")

class BaseRepository(Generic[ModelType]):

    model = None

    def __init__(self, db: Session):
        self.db = db

    def create(self, obj: ModelType) -> ModelType:

        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def get_by_id(self,object_id: int,):

        return self.db.get(self.model,object_id,)

    def delete(self, obj: ModelType):

        self.db.delete(obj)
        self.db.commit()
