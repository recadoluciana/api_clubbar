from datetime import date

from pydantic import BaseModel


class PainelPeriodo(BaseModel):
    inicio: date
    fim: date


class ParticipacaoLoja(BaseModel):
    loja_id: int
    nmloja: str
    valor: float
    percentual: float


class ProdutoMaisVendido(BaseModel):
    produto_id: int
    nome: str
    quantidade: int
    valor: float


class IngressoMaisVendido(BaseModel):
    lote_id: int
    nome: str
    quantidade: int
    valor: float


class PainelGerencialOut(BaseModel):
    periodo: PainelPeriodo
    total_hoje: float
    total_mes: float
    total_produtos_mes: float
    total_ingressos_mes: float
    pedidos_mes: int
    ingressos_vendidos_mes: int
    participacao_lojas: list[ParticipacaoLoja]
    produtos_mais_vendidos: list[ProdutoMaisVendido]
    ingressos_mais_vendidos: list[IngressoMaisVendido]
