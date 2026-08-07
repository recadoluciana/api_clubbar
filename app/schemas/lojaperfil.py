from pydantic import BaseModel
class LojaConteudoIn(BaseModel):
    dsdetalhadaloja: str | None = None
    fotos: list[dict] | None = None
    publicacoes: list[dict] | None = None
    videos: list[dict] | None = None
    configuracoes: dict | None = None
class LojaPoliticaIngressoIn(BaseModel):
    dspoliticaingresso: str | None = None
    urlmapaingressos: str | None = None
    dsmapaingressos: str | None = None
    dsorientacoesacesso: str | None = None
    configuracoes: dict | None = None
