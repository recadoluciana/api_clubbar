from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import Session

from app.core.security import get_usuario_logado
from app.database import get_db
from app.models.cliente import Cliente
from app.models.evento import Evento
from app.models.eventoatracao import EventoAtracao
from app.models.eventolote import EventoLote
from app.models.eventoloteglobal import EventoLoteGlobal
from app.models.eventolotepreco import EventoLotePreco
from app.models.eventosetor import EventoSetor
from app.models.itvenda import ItVenda
from app.models.loja import Loja
from app.models.produto import Produto
from app.models.venda import Venda
from app.schemas.painel_gerencial import EventoEmAndamentoOut, PainelGerencialOut


router = APIRouter(tags=["Painel gerencial"])
_CARGOS_GERENCIAL = {"SUPERADMIN", "ADMIN", "MANAGER"}
_FUSO_BRASIL = ZoneInfo("America/Sao_Paulo")


def _hoje_local() -> date:
    return datetime.now(_FUSO_BRASIL).date()


def _inicio_local_em_utc_naive(data_local: date) -> datetime:
    return datetime.combine(data_local, time.min, tzinfo=_FUSO_BRASIL).astimezone(
        timezone.utc
    ).replace(tzinfo=None)


def _referencia_utc() -> datetime:
    """Instante de referência serializável com o fuso UTC explícito."""
    return datetime.now(timezone.utc)


def _desde_em_utc_naive(desde: datetime) -> datetime:
    """Normaliza a referência recebida para comparação com colunas UTC-naive.

    Referências antigas do KPI não tinham sufixo de fuso e representavam o
    horário brasileiro. Mantemos essa compatibilidade durante a atualização.
    """
    if desde.tzinfo is None:
        return desde.replace(tzinfo=_FUSO_BRASIL).astimezone(timezone.utc).replace(
            tzinfo=None
        )
    return desde.astimezone(timezone.utc).replace(tzinfo=None)


def _inteiro_positivo(valor: object, nome: str) -> int:
    try:
        convertido = int(valor)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise HTTPException(status_code=403, detail=f"Token sem {nome} válido")
    if convertido <= 0:
        raise HTTPException(status_code=403, detail=f"Token sem {nome} válido")
    return convertido


def _extrair_escopo(
    usuario: dict,
    *,
    consolidado_por_organizacao: bool = False,
) -> tuple[int, int | None]:
    if usuario.get("role") != "usuario" and usuario.get("tipo") != "usuario":
        raise HTTPException(status_code=403, detail="Acesso permitido apenas a usuários parceiros")

    organizacao_id = _inteiro_positivo(usuario.get("organizacao_id"), "organizacao_id")
    cargo = str(usuario.get("dscargo") or "").strip().upper()

    if cargo not in _CARGOS_GERENCIAL:
        raise HTTPException(
            status_code=403,
            detail="O painel gerencial é exclusivo para SUPERADMIN, ADMIN e MANAGER",
        )

    if cargo == "MANAGER" and not consolidado_por_organizacao:
        return organizacao_id, _inteiro_positivo(usuario.get("loja_id"), "loja_id")

    # Administradores recebem a visão consolidada de toda a organização.
    return organizacao_id, None


def _dinheiro(valor: object) -> float:
    return float(round(Decimal(str(valor or 0)), 2))


def _periodo_selecionado(ano: int | None, mes: int | None) -> tuple[date, date]:
    hoje = _hoje_local()
    ano_final = ano if ano is not None else hoje.year
    mes_final = mes if mes is not None else hoje.month
    primeiro_dia = date(ano_final, mes_final, 1)
    if primeiro_dia > hoje.replace(day=1):
        raise HTTPException(status_code=422, detail="Nao e permitido consultar mes futuro.")
    if ano_final == hoje.year and mes_final == hoje.month:
        return primeiro_dia, hoje
    proximo_mes = (
        date(ano_final + 1, 1, 1)
        if mes_final == 12
        else date(ano_final, mes_final + 1, 1)
    )
    return primeiro_dia, proximo_mes - timedelta(days=1)


def _periodo_consulta(
    ano: int | None,
    mes: int | None,
    data_inicio: date | None,
    data_fim: date | None,
) -> tuple[date, date]:
    if data_inicio is None and data_fim is None:
        return _periodo_selecionado(ano, mes)
    if data_inicio is None or data_fim is None:
        raise HTTPException(
            status_code=422,
            detail="Informe a data inicial e a data final do período.",
        )
    if data_inicio > data_fim:
        raise HTTPException(status_code=422, detail="Período de consulta inválido.")
    if data_fim > _hoje_local():
        raise HTTPException(status_code=422, detail="Não é permitido consultar data futura.")
    return data_inicio, data_fim


def _local_em_utc_naive(momento_local: datetime) -> datetime:
    """Converte horários operacionais do evento (Brasília) para UTC no banco."""
    return momento_local.replace(tzinfo=_FUSO_BRASIL).astimezone(timezone.utc).replace(
        tzinfo=None
    )


def _fim_evento_operacional(db: Session, evento: Evento) -> datetime:
    """Usa o fim configurado, a última atração ou o prazo padrão de seis horas."""
    if evento.dtfimevento:
        return evento.dtfimevento
    fim_programacao = (
        db.query(func.max(EventoAtracao.dtfimatracao))
        .filter(EventoAtracao.evento_id == evento.evento_id)
        .scalar()
    )
    return fim_programacao or evento.dtinicioevento + timedelta(hours=6)


def _resumo_operacao_ingressos(
    db: Session,
    evento: Evento,
    agora: datetime,
) -> dict:
    linhas = (
        db.query(
            ItVenda.qtitvenda,
            ItVenda.vrunititvenda,
            ItVenda.identregaitvenda,
            EventoLotePreco.nrminutosaposinicio,
            EventoLotePreco.travarentradaaposlimite,
        )
        .join(Venda, Venda.venda_id == ItVenda.venda_id)
        .join(EventoLote, EventoLote.lote_id == ItVenda.lote_id)
        .outerjoin(
            EventoLotePreco,
            EventoLotePreco.lotepreco_id == ItVenda.lotepreco_id,
        )
        .filter(
            EventoLote.evento_id == evento.evento_id,
            Venda.sitvenda == "PAGA",
            ItVenda.tipoitem == "INGRESSO",
            ItVenda.sititvenda == "ATIVO",
        )
        .all()
    )
    vendidos = validados = pendentes = expirados = 0
    receita = Decimal("0")
    for linha in linhas:
        quantidade = int(linha.qtitvenda or 0)
        vendidos += quantidade
        receita += Decimal(str(linha.vrunititvenda or 0)) * quantidade
        if linha.identregaitvenda == "SIM":
            validados += quantidade
            continue
        minutos = linha.nrminutosaposinicio
        limite = (
            evento.dtinicioevento + timedelta(minutes=int(minutos))
            if linha.travarentradaaposlimite and minutos is not None
            else None
        )
        if limite is not None and agora > limite:
            expirados += quantidade
        else:
            pendentes += quantidade

    capacidade = evento.qtcapacidadeevento
    if capacidade is None:
        capacidade = (
            db.query(func.coalesce(func.sum(EventoSetor.qtcapacidade), 0))
            .filter(
                EventoSetor.evento_id == evento.evento_id,
                EventoSetor.sitsetor == "ATIVO",
            )
            .scalar()
        )
    return {
        "disponibilizados": int(capacidade or 0),
        "disponiveis": max(0, int(capacidade or 0) - vendidos),
        "vendidos_resgatados": vendidos,
        "validados_entregues": validados,
        "pendentes": pendentes,
        "expirados": expirados,
        "receita": _dinheiro(receita),
    }


def _resumo_operacao_produtos(
    db: Session,
    evento: Evento,
    fim_evento: datetime,
    agora: datetime,
) -> dict:
    """Produtos vendidos/resgatados durante a janela operacional do evento.

    O cardápio atual não possui estoque por unidade, por isso o número de
    disponibilizados fica nulo em vez de sugerir uma quantidade inexistente.
    """
    inicio_utc = _local_em_utc_naive(evento.dtinicioevento)
    fim_utc = _local_em_utc_naive(min(fim_evento, agora))
    linhas = (
        db.query(
            ItVenda.qtitvenda,
            ItVenda.vrunititvenda,
            ItVenda.vrtaxaitvenda,
            ItVenda.identregaitvenda,
            ItVenda.dtexpiraitvenda,
        )
        .join(Venda, Venda.venda_id == ItVenda.venda_id)
        .filter(
            Venda.organizacao_id == evento.organizacao_id,
            Venda.loja_id == evento.loja_id,
            Venda.sitvenda == "PAGA",
            Venda.dtcriacao >= inicio_utc,
            Venda.dtcriacao <= fim_utc,
            ItVenda.tipoitem == "PRODUTO",
            ItVenda.sititvenda == "ATIVO",
        )
        .all()
    )
    vendidos = entregues = pendentes = expirados = 0
    receita = Decimal("0")
    hoje = agora.date()
    for linha in linhas:
        quantidade = int(linha.qtitvenda or 0)
        vendidos += quantidade
        receita += (
            Decimal(str(linha.vrunititvenda or 0))
            * quantidade
            - Decimal(str(linha.vrtaxaitvenda or 0))
        )
        if linha.identregaitvenda == "SIM":
            entregues += quantidade
        elif linha.dtexpiraitvenda is not None and linha.dtexpiraitvenda < hoje:
            expirados += quantidade
        else:
            pendentes += quantidade
    return {
        "disponibilizados": None,
        "disponiveis": None,
        "vendidos_resgatados": vendidos,
        "validados_entregues": entregues,
        "pendentes": pendentes,
        "expirados": expirados,
        "receita": _dinheiro(receita),
    }


@router.get("/painel-gerencial/eventos-em-andamento", response_model=list[EventoEmAndamentoOut])
def eventos_em_andamento(
    db: Session = Depends(get_db),
    usuario: dict = Depends(get_usuario_logado),
):
    """Painel operacional em tempo real dos eventos que ainda não terminaram."""
    organizacao_id, loja_id = _extrair_escopo(
        usuario,
        consolidado_por_organizacao=True,
    )
    agora = datetime.now(_FUSO_BRASIL).replace(tzinfo=None)
    eventos_query = db.query(Evento, Loja.nmloja).join(
        Loja, Loja.loja_id == Evento.loja_id
    ).filter(
        Evento.organizacao_id == organizacao_id,
        Evento.statusevento == "ATIVO",
        Evento.dtinicioevento <= agora,
        or_(
            Evento.dtfimevento > agora,
            and_(
                Evento.dtfimevento.is_(None),
                Evento.dtinicioevento >= agora - timedelta(hours=24),
            ),
        ),
    )
    if loja_id is not None:
        eventos_query = eventos_query.filter(Evento.loja_id == loja_id)

    resposta = []
    for evento, nome_loja in eventos_query.order_by(Evento.dtinicioevento.asc()).all():
        fim = _fim_evento_operacional(db, evento)
        if fim <= agora:
            continue
        ingressos = _resumo_operacao_ingressos(db, evento, agora)
        produtos = _resumo_operacao_produtos(db, evento, fim, agora)
        resposta.append(
            {
                "evento_id": int(evento.evento_id),
                "nome": evento.nmtituloevento,
                "loja": nome_loja,
                "inicio": evento.dtinicioevento,
                "fim": fim,
                "ingressos": ingressos,
                "produtos": produtos,
                "receita_total": _dinheiro(
                    Decimal(str(ingressos["receita"]))
                    + Decimal(str(produtos["receita"]))
                ),
            }
        )
    return resposta


@router.get("/painel-gerencial", response_model=PainelGerencialOut)
def painel_gerencial(
    ano: Annotated[int | None, Query(ge=2000, le=2200)] = None,
    mes: Annotated[int | None, Query(ge=1, le=12)] = None,
    data_inicio: date | None = Query(default=None),
    data_fim: date | None = Query(default=None),
    consolidado: bool = Query(False),
    db: Session = Depends(get_db),
    usuario: dict = Depends(get_usuario_logado),
):
    organizacao_id, loja_id = _extrair_escopo(
        usuario,
        consolidado_por_organizacao=consolidado,
    )

    primeiro_dia, ultimo_dia = _periodo_consulta(
        ano, mes, data_inicio, data_fim
    )
    inicio_mes = _inicio_local_em_utc_naive(primeiro_dia)
    hoje = _hoje_local()
    inicio_hoje = _inicio_local_em_utc_naive(hoje)
    fim_hoje_exclusivo = _inicio_local_em_utc_naive(hoje + timedelta(days=1))
    fim_exclusivo = _inicio_local_em_utc_naive(ultimo_dia + timedelta(days=1))

    lojas_query = db.query(Loja.loja_id, Loja.nmloja).filter(
        Loja.organizacao_id == organizacao_id
    )
    if loja_id is not None:
        lojas_query = lojas_query.filter(Loja.loja_id == loja_id)

    lojas = lojas_query.order_by(Loja.nmloja, Loja.loja_id).all()
    if loja_id is not None and not lojas:
        raise HTTPException(status_code=403, detail="Loja não pertence à organização do usuário")

    filtros_mes = [
        Venda.organizacao_id == organizacao_id,
        Venda.sitvenda == "PAGA",
        Venda.dtcriacao >= inicio_mes,
        Venda.dtcriacao < fim_exclusivo,
    ]
    if loja_id is not None:
        filtros_mes.append(Venda.loja_id == loja_id)

    pedidos_mes = db.query(func.count(Venda.venda_id)).filter(*filtros_mes).scalar()
    produtos_pagos_mes = (
        db.query(func.count(Venda.venda_id))
        .filter(*filtros_mes, Venda.tipovenda == "PRODUTO")
        .scalar()
    )

    quantidade = func.coalesce(ItVenda.qtitvenda, 1)
    valor_bruto_item = quantidade * ItVenda.vrunititvenda
    eh_ingresso = ItVenda.tipoitem == "INGRESSO"
    eh_produto = ItVenda.tipoitem == "PRODUTO"
    # A taxa do Clubbar nao e receita do parceiro. Para produtos ela e
    # descontada do valor bruto; para ingressos consideramos apenas o valor-base.
    valor_liquido_item = case(
        (eh_ingresso, valor_bruto_item),
        else_=valor_bruto_item - func.coalesce(ItVenda.vrtaxaitvenda, 0),
    )

    totais_mes = db.query(
        func.coalesce(func.sum(case((eh_produto, valor_liquido_item), else_=0)), 0).label("produtos"),
        func.coalesce(func.sum(case((eh_ingresso, valor_liquido_item), else_=0)), 0).label("ingressos"),
    ).select_from(ItVenda).join(
        Venda, Venda.venda_id == ItVenda.venda_id
    ).filter(*filtros_mes, ItVenda.sititvenda == "ATIVO").one()

    filtros_hoje = [
        Venda.organizacao_id == organizacao_id,
        Venda.sitvenda == "PAGA",
        Venda.dtcriacao >= inicio_hoje,
        Venda.dtcriacao < fim_hoje_exclusivo,
    ]
    if loja_id is not None:
        filtros_hoje.append(Venda.loja_id == loja_id)

    total_hoje = db.query(
        func.coalesce(func.sum(valor_liquido_item), 0)
    ).select_from(ItVenda).join(
        Venda, Venda.venda_id == ItVenda.venda_id
    ).filter(*filtros_hoje, ItVenda.sititvenda == "ATIVO").scalar()

    resumo_quantidades = db.query(
        func.coalesce(
            func.sum(
                case(
                    (and_(eh_produto, ItVenda.vrunititvenda > 0), quantidade),
                    else_=0,
                )
            ),
            0,
        ).label("produtos_vendidos"),
        func.coalesce(
            func.sum(
                case(
                    (and_(eh_produto, ItVenda.vrunititvenda <= 0), quantidade),
                    else_=0,
                )
            ),
            0,
        ).label("produtos_cortesias"),
        func.coalesce(
            func.sum(
                case(
                    (and_(eh_produto, ItVenda.identregaitvenda == "SIM"), quantidade),
                    else_=0,
                )
            ),
            0,
        ).label("produtos_entregues"),
        func.coalesce(
            func.sum(
                case(
                    (and_(eh_produto, ItVenda.identregaitvenda != "SIM"), quantidade),
                    else_=0,
                )
            ),
            0,
        ).label("produtos_pendentes"),
        func.coalesce(
            func.sum(
                case(
                    (and_(eh_ingresso, ItVenda.vrunititvenda > 0), quantidade),
                    else_=0,
                )
            ),
            0,
        ).label("ingressos_vendidos"),
        func.coalesce(
            func.sum(
                case(
                    (and_(eh_ingresso, ItVenda.vrunititvenda <= 0), quantidade),
                    else_=0,
                )
            ),
            0,
        ).label("ingressos_cortesias"),
        func.coalesce(
            func.sum(
                case(
                    (and_(eh_ingresso, ItVenda.identregaitvenda == "SIM"), quantidade),
                    else_=0,
                )
            ),
            0,
        ).label("ingressos_validados"),
        func.coalesce(
            func.sum(
                case(
                    (and_(eh_ingresso, ItVenda.identregaitvenda != "SIM"), quantidade),
                    else_=0,
                )
            ),
            0,
        ).label("ingressos_pendentes"),
    ).select_from(ItVenda).join(Venda, Venda.venda_id == ItVenda.venda_id).filter(
        *filtros_mes,
        ItVenda.sititvenda == "ATIVO",
    ).one()

    # Este indicador é operacional e não é subconjunto das compras do
    # período: uma água comprada ontem pode ser retirada hoje. Por isso, sua
    # data de referência é a retirada, enquanto "Produtos" continua usando a
    # data da venda.
    filtros_retiradas_periodo = [
        Venda.organizacao_id == organizacao_id,
        Venda.sitvenda == "PAGA",
        ItVenda.tipoitem == "PRODUTO",
        ItVenda.sititvenda == "ATIVO",
        ItVenda.identregaitvenda == "SIM",
        ItVenda.dtentregaitvenda >= inicio_mes,
        ItVenda.dtentregaitvenda < fim_exclusivo,
    ]
    if loja_id is not None:
        filtros_retiradas_periodo.append(Venda.loja_id == loja_id)
    produtos_retirados_periodo = (
        db.query(func.coalesce(func.sum(quantidade), 0))
        .select_from(ItVenda)
        .join(Venda, Venda.venda_id == ItVenda.venda_id)
        .filter(*filtros_retiradas_periodo)
        .scalar()
    )

    participacao_rows = db.query(
        Venda.loja_id,
        func.coalesce(func.sum(valor_liquido_item), 0).label("valor"),
    ).select_from(ItVenda).join(
        Venda, Venda.venda_id == ItVenda.venda_id
    ).filter(*filtros_mes, ItVenda.sititvenda == "ATIVO").group_by(Venda.loja_id).all()
    valores_por_loja = {int(row.loja_id): _dinheiro(row.valor) for row in participacao_rows}
    total_produtos_mes = _dinheiro(totais_mes.produtos)
    total_ingressos_mes = _dinheiro(totais_mes.ingressos)
    total_mes = _dinheiro(Decimal(str(total_produtos_mes)) + Decimal(str(total_ingressos_mes)))

    participacao_lojas = []
    for loja in lojas:
        valor = valores_por_loja.get(int(loja.loja_id), 0.0)
        percentual = round((valor / total_mes) * 100, 2) if total_mes else 0.0
        participacao_lojas.append({
            "loja_id": int(loja.loja_id),
            "nmloja": loja.nmloja,
            "valor": valor,
            "percentual": percentual,
        })

    quantidade_produto = func.sum(ItVenda.qtitvenda).label("quantidade")
    valor_produto = func.sum(valor_liquido_item).label("valor")
    produtos_query = db.query(
        Produto.produto_id,
        Produto.nmproduto.label("nome"),
        quantidade_produto,
        valor_produto,
    ).join(ItVenda, ItVenda.produto_id == Produto.produto_id).join(
        Venda, Venda.venda_id == ItVenda.venda_id
    ).filter(
        *filtros_mes,
        Produto.organizacao_id == organizacao_id,
        ItVenda.tipoitem == "PRODUTO",
        ItVenda.sititvenda == "ATIVO",
    )
    if loja_id is not None:
        produtos_query = produtos_query.filter(Venda.loja_id == loja_id)
    produtos_rows = produtos_query.group_by(
        Produto.produto_id, Produto.nmproduto
    ).order_by(quantidade_produto.desc(), Produto.nmproduto).all()

    quantidade_ingresso = func.sum(ItVenda.qtitvenda).label("quantidade")
    valor_ingresso = func.sum(ItVenda.qtitvenda * ItVenda.vrunititvenda).label("valor")
    ingressos_query = db.query(
        EventoLote.lote_id,
        Evento.nmtituloevento,
        EventoLote.nmlote,
        quantidade_ingresso,
        valor_ingresso,
    ).join(ItVenda, ItVenda.lote_id == EventoLote.lote_id).join(
        Venda, Venda.venda_id == ItVenda.venda_id
    ).join(Evento, Evento.evento_id == EventoLote.evento_id).filter(
        *filtros_mes,
        EventoLote.organizacao_id == organizacao_id,
        Evento.organizacao_id == organizacao_id,
        ItVenda.sititvenda == "ATIVO",
    )
    if loja_id is not None:
        ingressos_query = ingressos_query.filter(
            EventoLote.loja_id == loja_id,
            Evento.loja_id == loja_id,
        )
    ingressos_rows = ingressos_query.group_by(
        EventoLote.lote_id,
        Evento.nmtituloevento,
        EventoLote.nmlote,
    ).order_by(quantidade_ingresso.desc(), Evento.nmtituloevento, EventoLote.nmlote).all()

    return {
        "periodo": {"inicio": primeiro_dia, "fim": ultimo_dia},
        "total_hoje": _dinheiro(total_hoje),
        "total_mes": total_mes,
        "total_produtos_mes": total_produtos_mes,
        "total_ingressos_mes": total_ingressos_mes,
        "pedidos_mes": int(pedidos_mes or 0),
        "produtos_pagos_mes": int(produtos_pagos_mes or 0),
        "produtos_vendidos_mes": int(resumo_quantidades.produtos_vendidos or 0),
        "produtos_cortesias_mes": int(resumo_quantidades.produtos_cortesias or 0),
        "produtos_entregues": int(resumo_quantidades.produtos_entregues or 0),
        "produtos_pendentes": int(resumo_quantidades.produtos_pendentes or 0),
        "produtos_retirados_periodo": int(produtos_retirados_periodo or 0),
        "ingressos_vendidos_mes": int(resumo_quantidades.ingressos_vendidos or 0),
        "ingressos_cortesias_mes": int(resumo_quantidades.ingressos_cortesias or 0),
        "ingressos_validados": int(resumo_quantidades.ingressos_validados or 0),
        "ingressos_pendentes": int(resumo_quantidades.ingressos_pendentes or 0),
        "participacao_lojas": participacao_lojas,
        "produtos_mais_vendidos": [
            {
                "produto_id": int(row.produto_id),
                "nome": row.nome,
                "quantidade": int(row.quantidade or 0),
                "valor": _dinheiro(row.valor),
            }
            for row in produtos_rows
        ],
        "ingressos_mais_vendidos": [
            {
                "lote_id": int(row.lote_id),
                "nome": f"{row.nmtituloevento} - {row.nmlote}",
                "quantidade": int(row.quantidade or 0),
                "valor": _dinheiro(row.valor),
            }
            for row in ingressos_rows
        ],
    }


@router.get("/painel-gerencial/detalhes-vendas")
def detalhes_vendas(
    tipo: str = Query(pattern="^(PRODUTOS|INGRESSOS|RETIRADAS)$"),
    ano: Annotated[int | None, Query(ge=2000, le=2200)] = None,
    mes: Annotated[int | None, Query(ge=1, le=12)] = None,
    data_inicio: date | None = Query(default=None),
    data_fim: date | None = Query(default=None),
    limite: Annotated[int, Query(ge=1, le=1000)] = 500,
    db: Session = Depends(get_db),
    usuario: dict = Depends(get_usuario_logado),
):
    """Lista vendas ou retiradas no período exibido pelo painel KPI.

    O KPI é consolidado por organização, inclusive para o perfil MANAGER. Os
    dados retornados são apenas operacionais: não incluem QR Codes, senhas,
    links de pagamento nem identificadores de transação.
    """
    organizacao_id, _ = _extrair_escopo(
        usuario,
        consolidado_por_organizacao=True,
    )
    primeiro_dia, ultimo_dia = _periodo_consulta(
        ano, mes, data_inicio, data_fim
    )
    inicio_mes = _inicio_local_em_utc_naive(primeiro_dia)
    fim_exclusivo = _inicio_local_em_utc_naive(ultimo_dia + timedelta(days=1))
    filtros = [
        Venda.organizacao_id == organizacao_id,
        Venda.sitvenda == "PAGA",
        ItVenda.sititvenda == "ATIVO",
    ]

    if tipo == "RETIRADAS":
        filtros.extend([
            ItVenda.tipoitem == "PRODUTO",
            ItVenda.identregaitvenda == "SIM",
            ItVenda.dtentregaitvenda >= inicio_mes,
            ItVenda.dtentregaitvenda < fim_exclusivo,
        ])
    else:
        filtros.extend([
            Venda.dtcriacao >= inicio_mes,
            Venda.dtcriacao < fim_exclusivo,
        ])

    if tipo in {"PRODUTOS", "RETIRADAS"}:
        rows = (
            db.query(
                ItVenda.itvenda_id,
                ItVenda.qtitvenda,
                ItVenda.vrunititvenda,
                ItVenda.vrtaxaitvenda,
                ItVenda.identregaitvenda,
                ItVenda.dtentregaitvenda,
                ItVenda.nmuserentregaitvenda,
                ItVenda.idcontrolebar,
                ItVenda.nrmesa,
                Venda.venda_id,
                Venda.dtcriacao.label("dtcompra"),
                Loja.nmloja,
                Cliente.nmcliente,
                Cliente.emailcliente,
                Cliente.nrtelcliente,
                Cliente.nrcpfcliente,
                Produto.nmproduto,
            )
            .join(Venda, Venda.venda_id == ItVenda.venda_id)
            .join(Loja, Loja.loja_id == Venda.loja_id)
            .outerjoin(Cliente, Cliente.cliente_id == Venda.cliente_id)
            .join(Produto, Produto.produto_id == ItVenda.produto_id)
            .filter(*filtros, ItVenda.tipoitem == "PRODUTO")
            .order_by(
                ItVenda.dtentregaitvenda.desc()
                if tipo == "RETIRADAS"
                else Venda.dtcriacao.desc(),
                ItVenda.itvenda_id.desc(),
            )
            .limit(limite)
            .all()
        )
        itens = []
        for row in rows:
            quantidade = int(row.qtitvenda or 0)
            itens.append(
                {
                    "itvenda_id": int(row.itvenda_id),
                    "venda_id": int(row.venda_id),
                    "produto": row.nmproduto,
                    "loja": row.nmloja,
                    "cliente": row.nmcliente or "Cliente não identificado",
                    "email_cliente": row.emailcliente or "",
                    "telefone_cliente": row.nrtelcliente or "",
                    "cpf_cliente": row.nrcpfcliente or "",
                    "quantidade": quantidade,
                    "preco_unitario": _dinheiro(row.vrunititvenda),
                    "taxa": _dinheiro(row.vrtaxaitvenda),
                    "valor_total": _dinheiro(
                        Decimal(str(row.vrunititvenda or 0)) * quantidade
                    ),
                    "data_compra": row.dtcompra.replace(tzinfo=timezone.utc),
                    "retirado": (row.identregaitvenda or "NAO").upper() == "SIM",
                    "data_retirada": (
                        row.dtentregaitvenda.replace(tzinfo=timezone.utc)
                        if row.dtentregaitvenda
                        else None
                    ),
                    "responsavel_retirada": row.nmuserentregaitvenda or "",
                    "cortesia": Decimal(str(row.vrunititvenda or 0)) <= 0,
                    "situacao_bar": str(row.idcontrolebar or "PENDENTE"),
                    "mesa": row.nrmesa or "",
                }
            )
    else:
        rows = (
            db.query(
                ItVenda.itvenda_id,
                ItVenda.qtitvenda,
                ItVenda.vrunititvenda,
                ItVenda.vrtaxaitvenda,
                ItVenda.identregaitvenda,
                ItVenda.dtentregaitvenda,
                ItVenda.nmparticipante,
                ItVenda.cpfparticipante,
                ItVenda.nmmodalidadesnapshot,
                Venda.venda_id,
                Venda.dtcriacao.label("dtcompra"),
                Loja.nmloja,
                Cliente.nmcliente,
                Cliente.emailcliente,
                Cliente.nrtelcliente,
                Cliente.nrcpfcliente,
                Evento.nmtituloevento,
                Evento.dtinicioevento,
                EventoLoteGlobal.nrlote,
                EventoLoteGlobal.nmlote,
                EventoSetor.nmsetor,
                EventoLotePreco.nmpreco,
                EventoLotePreco.tipopreco,
            )
            .join(Venda, Venda.venda_id == ItVenda.venda_id)
            .join(Loja, Loja.loja_id == Venda.loja_id)
            .outerjoin(Cliente, Cliente.cliente_id == Venda.cliente_id)
            .join(EventoLote, EventoLote.lote_id == ItVenda.lote_id)
            .join(
                EventoLoteGlobal,
                EventoLoteGlobal.loteglobal_id == EventoLote.loteglobal_id,
            )
            .join(Evento, Evento.evento_id == EventoLoteGlobal.evento_id)
            .outerjoin(
                EventoSetor,
                EventoSetor.eventosetor_id == EventoLote.eventosetor_id,
            )
            .outerjoin(
                EventoLotePreco,
                EventoLotePreco.lotepreco_id == ItVenda.lotepreco_id,
            )
            .filter(
                *filtros,
                ItVenda.tipoitem == "INGRESSO",
                Evento.organizacao_id == organizacao_id,
            )
            .order_by(Venda.dtcriacao.desc(), ItVenda.itvenda_id.desc())
            .limit(limite)
            .all()
        )
        itens = []
        for row in rows:
            quantidade = int(row.qtitvenda or 0)
            itens.append(
                {
                    "itvenda_id": int(row.itvenda_id),
                    "venda_id": int(row.venda_id),
                    "evento": row.nmtituloevento,
                    # A programação do evento é um horário civil brasileiro.
                    "data_evento": row.dtinicioevento,
                    "loja": row.nmloja,
                    "cliente": row.nmcliente or "Cliente não identificado",
                    "email_cliente": row.emailcliente or "",
                    "telefone_cliente": row.nrtelcliente or "",
                    "cpf_cliente": row.nrcpfcliente or "",
                    "participante": row.nmparticipante or "Não informado",
                    "cpf_participante": row.cpfparticipante or "",
                    "lote": f"{int(row.nrlote)}º • {row.nmlote or 'Lote não informado'}",
                    "setor": row.nmsetor or "Setor único",
                    "modalidade": (
                        row.nmmodalidadesnapshot
                        or row.nmpreco
                        or row.tipopreco
                        or "Ingresso"
                    ),
                    "quantidade": quantidade,
                    "preco_unitario": _dinheiro(row.vrunititvenda),
                    "taxa": _dinheiro(row.vrtaxaitvenda),
                    "valor_total": _dinheiro(
                        Decimal(str(row.vrunititvenda or 0)) * quantidade
                    ),
                    "data_compra": row.dtcompra.replace(tzinfo=timezone.utc),
                    "utilizado": (row.identregaitvenda or "NAO").upper() == "SIM",
                    "data_validacao": (
                        row.dtentregaitvenda.replace(tzinfo=timezone.utc)
                        if row.dtentregaitvenda
                        else None
                    ),
                }
            )

    return {
        "tipo": tipo,
        "periodo": {"inicio": primeiro_dia, "fim": ultimo_dia},
        "itens": itens,
        "limite": limite,
    }


@router.get("/painel-gerencial/notificacoes-vendas")
def notificacoes_vendas(
    desde: datetime | None = None,
    db: Session = Depends(get_db),
    usuario: dict = Depends(get_usuario_logado),
):
    """Retorna vendas novas ou canceladas depois da última consulta do KPI.

    O KPI é sempre consolidado pela organização, inclusive para o perfil
    MANAGER. Sem `desde`, a rota apenas estabelece uma referência para evitar
    avisos antigos logo ao abrir o painel.
    """
    organizacao_id, _ = _extrair_escopo(
        usuario,
        consolidado_por_organizacao=True,
    )
    referencia = _referencia_utc()
    if desde is None:
        return {"referencia": referencia, "vendas": []}
    desde = _desde_em_utc_naive(desde)

    momento_venda = func.coalesce(Venda.dtultatu, Venda.dtcriacao)
    movimentacoes = (
        db.query(
            Venda.venda_id,
            Venda.tipovenda,
            Venda.sitvenda,
            momento_venda.label("momento"),
            func.coalesce(Venda.totalvenda, 0).label("valor"),
        )
        .filter(
            Venda.organizacao_id == organizacao_id,
            Venda.sitvenda.in_(("PAGA", "CANCELADA")),
            momento_venda > desde,
        )
        .order_by(momento_venda.asc(), Venda.venda_id.asc())
        .limit(30)
        .all()
    )
    return {
        "referencia": referencia,
        "vendas": [
            {
                "venda_id": int(movimentacao.venda_id),
                "evento": (
                    "CANCELAMENTO"
                    if movimentacao.sitvenda == "CANCELADA"
                    else "VENDA"
                ),
                "tipo": str(movimentacao.tipovenda),
                "valor": _dinheiro(movimentacao.valor),
                # As vendas são registradas em UTC. O sufixo explícito evita
                # que o app interprete este valor como horário local.
                "momento": movimentacao.momento.replace(tzinfo=timezone.utc),
            }
            for movimentacao in movimentacoes
        ],
    }
