from datetime import datetime

from pydantic import BaseModel


class DocumentResponse(BaseModel):

    id: int
    file_name: str
    status: str
    created_at: datetime

    model_config = {
        "from_attributes": True
    }
