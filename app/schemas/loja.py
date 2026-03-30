from pydantic import BaseModel

class LojaCreate(BaseModel):
    organizacao_id: int
    nmloja: str
    dsbairroloja: Optional[str] = None
    nrtelloja: Optional[str] = None
    dshorarioloja: Optional[str] = None
    nrdiavalidade: Optional[int] = None

class LojaUpdate(BaseModel):
    organizacao_id: Optional[int] = None
    nmloja: Optional[str] = None
    dsbairroloja: Optional[str] = None
    nrtelloja: Optional[str] = None
    dshorarioloja: Optional[str] = None
    nrdiavalidade: Optional[int] = None