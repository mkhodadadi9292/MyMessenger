from pydantic import BaseModel


class StartUploadResponse(BaseModel):
    session_id: str
