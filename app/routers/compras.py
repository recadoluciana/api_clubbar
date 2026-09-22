from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.venda import Venda
from app.models.itvenda import ItVenda
from app.models.produto import Produto
from app.models.loja import Loja
from app.models.eventolote import EventoLote
from app.models.eventolotepreco import EventoLotePreco
from app.models.eventosetor import EventoSetor
from app.models.evento import Evento
from app.models.itvendaparticipantehistorico import ItVendaParticipanteHistorico

from app.utils.datetime_utils import formatar_data_br

router = APIRouter(prefix="/compras", tags=["compras"])


def _descricao_tipo_ingresso(
    nome_setor: str | None,
    nome_preco: str | None,
    tipo_preco: str | None,
    tipo_beneficio: str | None,
) -> str:
    modalidade = (tipo_preco or "").upper()
    beneficio = (tipo_beneficio or "").upper()
    nomes_modalidade = {
        "INTEIRA": "Inteira",
        "MEIA_LEGAL": "Meia-entrada",
        "MEIA_IDOSO": "Meia-entrada",
    }
    nomes_beneficio = {
        "ESTUDANTE": "Estudante",
        "JOVEM_BAIXA_RENDA": "Jovem de baixa renda",
        "PCD": "Pessoa com deficiência",
        "ACOMPANHANTE_PCD": "Acompanhante PCD",
        "IDOSO": "Pessoa idosa",
    }
    partes = [
        parte
        for parte in [nome_setor, nome_preco or nomes_modalidade.get(modalidade, "Ingresso")]
        if parte
    ]
    descricao = " • ".join(partes)
    if modalidade.startswith("MEIA") and beneficio:
        nome_beneficio = nomes_beneficio.get(
            beneficio, beneficio.replace("_", " ").title()
        )
        if nome_beneficio.lower() not in descricao.lower():
            descricao = f"{descricao} • {nome_beneficio}"
    return descricao


@router.get("")
def listar_compras(
    cliente_id: int,
    incluir_itens: bool = True,
    db: Session = Depends(get_db),
):
    # 1) Vendas do cliente + nome da loja + logo da loja
    vendas = (
        db.query(Venda, Loja.nmloja, Loja.urllogoloja)
        .join(
            Loja,
            (Loja.organizacao_id == Venda.organizacao_id)
            & (Loja.loja_id == Venda.loja_id),
        )
        .filter(
            Venda.cliente_id == cliente_id,
            Venda.sitvenda.in_(["PAGA", "CANCELADA"])
        )
        .order_by(Venda.dtcriacao.desc())
        .all()
    )

    if not vendas:
        return []

    if not incluir_itens:
        return [
            {
                "venda_id": v.venda_id,
                "organizacao_id": v.organizacao_id,
                "loja_id": v.loja_id,
                "nmloja": nmloja,
                "urllogoloja": urllogoloja,
                "cliente_id": v.cliente_id,
                "sitvenda": v.sitvenda,
                "totalvenda": float(v.totalvenda),
                "dtcriacao": formatar_data_br(v.dtcriacao),
                "carrinho_id": v.carrinho_id,
                "dsplataforma": v.dsplataforma,
            }
            for v, nmloja, urllogoloja in vendas
        ]

    venda_ids = [v.venda_id for v, _, _ in vendas]

    # 2) Itens + nome do produto + tipo do produto
    itens_rows = (
        db.query(
            ItVenda,
            Produto.nmproduto,
            Evento.nmtituloevento,
            EventoLote.nmlote,
            EventoLote.nrlote,
            EventoLotePreco.nmpreco,
            EventoLotePreco.tipopreco,
            EventoSetor.nmsetor,
        )
        .outerjoin(Produto, Produto.produto_id == ItVenda.produto_id)
        .outerjoin(EventoLote, EventoLote.lote_id == ItVenda.lote_id)
        .outerjoin(EventoLotePreco, EventoLotePreco.lotepreco_id == ItVenda.lotepreco_id)
        .outerjoin(EventoSetor, EventoSetor.eventosetor_id == EventoLote.eventosetor_id)
        .outerjoin(Evento, Evento.evento_id == EventoLote.evento_id)
        .filter(ItVenda.venda_id.in_(venda_ids))
        .all()
    )

    itvenda_ids = [it.itvenda_id for it, *_ in itens_rows]
    historicos_por_item = {}
    if itvenda_ids:
        historicos = (
            db.query(ItVendaParticipanteHistorico)
            .filter(ItVendaParticipanteHistorico.itvenda_id.in_(itvenda_ids))
            .order_by(ItVendaParticipanteHistorico.dttransferencia.asc())
            .all()
        )
        for historico in historicos:
            historicos_por_item.setdefault(historico.itvenda_id, []).append({
                "nmparticipanteanterior": historico.nmparticipanteanterior,
                "cpfparticipanteanterior": historico.cpfparticipanteanterior,
                "nmparticipantenovo": historico.nmparticipantenovo,
                "cpfparticipantenovo": historico.cpfparticipantenovo,
                "dttransferencia": formatar_data_br(historico.dttransferencia),
            })

    itens_por_venda = {}
    for (
        it,
        nmproduto,
        nmevento,
        nmlote,
        nrlote,
        nmpreco,
        tipopreco,
        nmsetor,
    ) in itens_rows:
        itens_por_venda.setdefault(it.venda_id, []).append({
            "itvenda_id": getattr(it, "itvenda_id", None),
            "produto_id": getattr(it, "produto_id", None),
            "nmproduto": nmproduto or nmevento or "Ingresso",
            "idtipoproduto": "I" if it.tipoitem == "INGRESSO" else "P",
            "qtitvenda": it.qtitvenda,
            "vrunititvenda": float(it.vrunititvenda),
            "vrtaxaitvenda": float(it.vrtaxaitvenda) if it.vrtaxaitvenda is not None else 0.0,
            "identregaitvenda": it.identregaitvenda,
            "dtentregaitvenda": formatar_data_br(it.dtentregaitvenda),
            "userentregaitvenda": it.userentregaitvenda,
            "nmuserentregaitvenda": it.nmuserentregaitvenda,
            "dsobsitvenda": it.dsobsitvenda,
            "sititvenda": it.sititvenda,
            "dtcancelamento": formatar_data_br(it.dtcancelamento),
            "vrreembolso": float(it.vrreembolso) if it.vrreembolso is not None else None,
            "idreembolso": it.idreembolso,
            "nmparticipante": it.nmparticipante,
            "cpfparticipante": it.cpfparticipante,
            "lote": nmlote or (f"Lote {nrlote}" if nrlote else None),
            "tipo_ingresso": _descricao_tipo_ingresso(
                nmsetor,
                nmpreco,
                tipopreco,
                it.tipobeneficio,
            ) if it.tipoitem == "INGRESSO" else None,
            "historico_participantes": historicos_por_item.get(it.itvenda_id, []),
        })

    # 3) Resposta final
    resp = []
    for v, nmloja, urllogoloja in vendas:
        resp.append({
            "venda_id": v.venda_id,
            "organizacao_id": v.organizacao_id,
            "loja_id": v.loja_id,
            "nmloja": nmloja,
            "urllogoloja": urllogoloja,   # ✅ novo
            "cliente_id": v.cliente_id,
            "dsplataforma": v.dsplataforma,
            "sitvenda": v.sitvenda,
            "totalvenda": float(v.totalvenda),
            "dtcriacao": formatar_data_br(v.dtcriacao),
            "dtultatu": formatar_data_br(v.dtultatu),
            "carrinho_id": v.carrinho_id,
            "itens": itens_por_venda.get(v.venda_id, []),
        })

    return resp
