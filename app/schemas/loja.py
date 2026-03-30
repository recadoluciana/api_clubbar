from pydantic import BaseModel

class LojaCreate(BaseModel):
    organizacao_id: int
    nmloja: str
    dsbairroloja: str | None = None
    nrtelloja: str | None = None
    dshorarioloja: str | None = None
    nrdiavalidade: int | None = 0