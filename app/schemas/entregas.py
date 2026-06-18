from pydantic import BaseModel

class LojaRetiradaOut(BaseModel):
    loja_id: int
    nmloja: str
    dsbairroloja: str
    total_itens: int

class AlterarParticipanteIn(BaseModel):
    nmparticipante: str
    cpfparticipante: str