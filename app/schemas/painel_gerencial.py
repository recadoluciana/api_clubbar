from datetime import date, datetime

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


class OperacaoEventoItem(BaseModel):
    # Produtos ainda não possuem controle de estoque por unidade no cardápio.
    # Por isso, esse campo pode ser nulo apenas para produtos.
    disponibilizados: int | None
    disponiveis: int | None
    vendidos_resgatados: int
    validados_entregues: int
    pendentes: int
    expirados: int
    receita: float


class EventoEmAndamentoOut(BaseModel):
    evento_id: int
    nome: str
    loja: str
    inicio: datetime
    fim: datetime
    ingressos: OperacaoEventoItem
    produtos_normais: OperacaoEventoItem
    produtos_cortesias: OperacaoEventoItem
    receita_total: float


class PainelGerencialOut(BaseModel):
    periodo: PainelPeriodo
    total_hoje: float
    total_mes: float
    total_produtos_mes: float
    total_ingressos_mes: float
    pedidos_mes: int
    produtos_pagos_mes: int
    produtos_vendidos_mes: int
    produtos_cortesias_mes: int
    produtos_entregues: int
    produtos_pendentes: int
    produtos_retirados_periodo: int
    ingressos_vendidos_mes: int
    ingressos_cortesias_mes: int
    ingressos_validados: int
    ingressos_pendentes: int
    participacao_lojas: list[ParticipacaoLoja]
    produtos_mais_vendidos: list[ProdutoMaisVendido]
    ingressos_mais_vendidos: list[IngressoMaisVendido]
