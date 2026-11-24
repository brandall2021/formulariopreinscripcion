from datetime import datetime
from pydantic import BaseModel

class SolicitudOut(BaseModel):
    id: int
    numero: str | None = None
    dni: str
    tipo_ingresante: str
    estado: str
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

class ConfirmacionOut(BaseModel):
    numero: str
    fecha: datetime
    estado: str
    comprobante: str
