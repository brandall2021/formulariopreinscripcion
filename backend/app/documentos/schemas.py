from pydantic import BaseModel

class UploadUrlOut(BaseModel):
    url: str
    expires_in: int
    documento_id: int

class DownloadUrlOut(BaseModel):
    url: str
    expires_in: int

class ValidacionOut(BaseModel):
    object_key: str
    estado: str
