from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.cliente_auth import exigir_cliente_autenticado
from app.core.permissoes_loja import validar_mutacao_loja
from app.core.security import get_usuario_logado, get_usuario_opcional
from app.database import get_db
from app.models.beneficio_produto import BeneficioProdutoCampanha, BeneficioProdutoResgate
from app.models.loja import Loja
from app.models.produto import Produto
from app.models.carrinho import Carrinho
from app.models.itcarrinho import ItCarrinho
from app.models.venda import Venda
from app.models.itvenda import ItVenda
from app.models.pagvenda import PagVenda
from app.services.venda_service import gerar_token_qr
from app.services.desconto_roleta_service import melhor_preco_roleta
from app.services.pagamento_status_service import set_venda_como_paga
from app.utils.datetime_utils import FUSO_BRASIL

router = APIRouter(prefix="/beneficios-produtos", tags=["Benefícios de produtos"])
PERCENTUAIS_ROLETA = (0, 10, 20)
JANELA_DESCONTO_DIAS = 10

def _agora() -> datetime:
    return datetime.now(FUSO_BRASIL).replace(tzinfo=None)


class CampanhaIn(BaseModel):
    organizacao_id: int
    loja_id: int
    produto_id: int
    tipo: str = Field(pattern="^(CORTESIA|PERCENTUAL|PACOTE|ROLETA)$")
    nmcampanha: str = Field(min_length=2, max_length=120)
    dthrinicio: datetime
    dthrfim: datetime | None = None
    qtlimite: int | None = Field(default=None, ge=1)
    limite_cliente_dia: int = Field(default=1, ge=1, le=10)
    qtitenspacote: int | None = Field(default=None, ge=2, le=99)
    vrpacote: Decimal | None = Field(
        default=None, gt=0, max_digits=10, decimal_places=2,
    )
    percentual_desconto: Decimal | None = Field(
        default=None, gt=0, lt=100, max_digits=5, decimal_places=2,
    )
    situacao: str = Field(default="ATIVA", pattern="^(ATIVA|INATIVA)$")

    @model_validator(mode="after")
    def periodo_valido(self):
        if self.dthrfim is not None and self.dthrfim <= self.dthrinicio:
            raise ValueError("O fim da campanha deve ser posterior ao início.")
        if self.tipo == "PACOTE":
            if self.qtitenspacote is None or self.vrpacote is None:
                raise ValueError("Informe a quantidade e o preço da promoção em pacote.")
            self.percentual_desconto = None
        elif self.tipo == "PERCENTUAL":
            if self.percentual_desconto is None:
                raise ValueError("Informe o percentual de desconto da promoção.")
            self.qtitenspacote = None
            self.vrpacote = None
        else:
            self.qtitenspacote = None
            self.vrpacote = None
            self.percentual_desconto = None
        return self


class GiroIn(BaseModel):
    cliente_id: int
    carrinho_id: int | None = None


def _status_periodo(item: BeneficioProdutoCampanha, agora: datetime | None = None) -> str:
    agora = agora or _agora()
    if item.situacao != "ATIVA":
        return "INATIVA"
    if item.dthrinicio > agora:
        return "AGENDADA"
    if item.dthrfim is not None and item.dthrfim < agora:
        return "ENCERRADA"
    return "ATIVA"


def _periodo_ativo(item: BeneficioProdutoCampanha, agora: datetime | None = None) -> bool:
    return _status_periodo(item, agora) == "ATIVA"


def _periodos_se_sobrepoem(
    inicio_a: datetime,
    fim_a: datetime | None,
    inicio_b: datetime,
    fim_b: datetime | None,
) -> bool:
    """Retorna se dois intervalos inclusivos de campanha se cruzam."""
    return (
        (fim_a is None or inicio_b <= fim_a)
        and (fim_b is None or inicio_a <= fim_b)
    )


def _validar_nao_sobrepoe_campanha(
    db: Session,
    dados: CampanhaIn,
    *,
    campanha_id_atual: int | None = None,
) -> None:
    """Evita que o Client receba duas ofertas equivalentes para o mesmo produto."""
    if dados.situacao != "ATIVA":
        return

    filtros = [
        BeneficioProdutoCampanha.organizacao_id == dados.organizacao_id,
        BeneficioProdutoCampanha.loja_id == dados.loja_id,
        BeneficioProdutoCampanha.produto_id == dados.produto_id,
        BeneficioProdutoCampanha.tipo == dados.tipo,
        BeneficioProdutoCampanha.situacao == "ATIVA",
        or_(
            BeneficioProdutoCampanha.dthrfim.is_(None),
            BeneficioProdutoCampanha.dthrfim >= dados.dthrinicio,
        ),
    ]
    if dados.dthrfim is not None:
        filtros.append(BeneficioProdutoCampanha.dthrinicio <= dados.dthrfim)
    if campanha_id_atual is not None:
        filtros.append(
            BeneficioProdutoCampanha.beneficioprodutocampanha_id
            != campanha_id_atual
        )

    conflito = db.query(BeneficioProdutoCampanha).filter(*filtros).first()
    if not conflito:
        return

    tipos = {
        "CORTESIA": "cortesia",
        "PERCENTUAL": "promoção percentual",
        "PACOTE": "promoção por quantidade",
        "ROLETA": "roleta",
    }
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            f"Já existe uma campanha de {tipos[dados.tipo]} ativa para este produto "
            "no período informado. Altere o período ou edite a campanha existente."
        ),
    )


def _campanha_out(item: BeneficioProdutoCampanha, *, resgates: int | None = None, nmproduto: str | None = None) -> dict:
    dados = {
        "campanha_id": int(item.beneficioprodutocampanha_id),
        "organizacao_id": int(item.organizacao_id), "loja_id": int(item.loja_id),
        "produto_id": int(item.produto_id), "tipo": item.tipo, "nmcampanha": item.nmcampanha,
        "dthrinicio": item.dthrinicio, "dthrfim": item.dthrfim, "qtlimite": item.qtlimite,
        "limite_cliente_dia": int(item.limite_cliente_dia or 1), "situacao": item.situacao,
        "status_periodo": _status_periodo(item),
        "qtitenspacote": int(item.qtitenspacote) if item.qtitenspacote else None,
        "vrpacote": float(item.vrpacote) if item.vrpacote is not None else None,
        "percentual_desconto": (
            float(item.percentual_desconto)
            if item.percentual_desconto is not None
            else None
        ),
    }
    if resgates is not None:
        dados["resgates"] = resgates
        dados["restantes"] = None if item.qtlimite is None else max(0, int(item.qtlimite) - resgates)
    if nmproduto is not None:
        dados["nmproduto"] = nmproduto
    return dados


def _total_resgates_validos(db: Session, campanha_id: int) -> int:
    """Conta somente benefícios que ainda podem ser usados ou já foram usados.

    Um prêmio cancelado quando o cliente decide girar novamente não deve consumir
    a quantidade total da campanha.
    """
    return int(
        db.query(func.count(BeneficioProdutoResgate.beneficioprodutoresgate_id))
        .filter(
            BeneficioProdutoResgate.campanha_id == campanha_id,
            BeneficioProdutoResgate.situacao.in_(("DISPONIVEL", "USADO")),
        )
        .scalar()
        or 0
    )


def _total_roletas_utilizadas(db: Session, campanha_id: int) -> int:
    return int(db.query(func.count(BeneficioProdutoResgate.beneficioprodutoresgate_id))
        .filter(BeneficioProdutoResgate.campanha_id == campanha_id,
                BeneficioProdutoResgate.situacao == "USADO").scalar() or 0)


def _total_pacotes_vendidos(
    db: Session, campanha: BeneficioProdutoCampanha,
) -> int:
    """Cada pacote gera uma ficha por unidade; conta os pacotes, não fichas."""
    unidades = int(campanha.qtitenspacote or 1)
    fichas = int(
        db.query(func.count(ItVenda.itvenda_id))
        .join(Venda, Venda.venda_id == ItVenda.venda_id)
        .filter(
            ItVenda.beneficioprodutocampanha_id
            == campanha.beneficioprodutocampanha_id,
            ItVenda.sititvenda == "ATIVO",
            Venda.sitvenda.in_(("PENDENTE", "PAGA")),
        )
        .scalar()
        or 0
    )
    return fichas // unidades


def _total_unidades_promocionais(
    db: Session, campanha: BeneficioProdutoCampanha,
) -> int:
    """Conta unidades já vendidas em campanhas percentuais."""
    return int(
        db.query(func.count(ItVenda.itvenda_id))
        .join(Venda, Venda.venda_id == ItVenda.venda_id)
        .filter(
            ItVenda.beneficioprodutocampanha_id
            == campanha.beneficioprodutocampanha_id,
            ItVenda.sititvenda == "ATIVO",
            Venda.sitvenda.in_(("PENDENTE", "PAGA")),
        )
        .scalar()
        or 0
    )


def _tem_cortesia_pendente(db: Session, *, cliente_id: int, produto_id: int) -> bool:
    """Cortesia válida, já emitida e ainda não retirada para o mesmo produto."""
    hoje = _agora().date()
    return (
        db.query(ItVenda.itvenda_id)
        .join(Venda, Venda.venda_id == ItVenda.venda_id)
        .filter(
            Venda.cliente_id == cliente_id,
            Venda.sitvenda == "PAGA",
            ItVenda.tipoitem == "PRODUTO",
            ItVenda.produto_id == produto_id,
            ItVenda.sititvenda == "ATIVO",
            ItVenda.identregaitvenda == "NAO",
            ItVenda.vrunititvenda <= 0,
            (ItVenda.dtexpiraitvenda.is_(None) | (ItVenda.dtexpiraitvenda >= hoje)),
        )
        .first()
        is not None
    )


def _tem_desconto_recente(db: Session, *, cliente_id: int, produto_id: int, agora: datetime) -> bool:
    """Verifica em itvenda uma compra paga com desconto da roleta nos últimos 10 dias."""
    return (
        db.query(ItVenda.itvenda_id)
        .join(Venda, Venda.venda_id == ItVenda.venda_id)
        .join(
            BeneficioProdutoResgate,
            BeneficioProdutoResgate.beneficioprodutoresgate_id
            == ItVenda.beneficioprodutoresgate_id,
        )
        .filter(
            Venda.cliente_id == cliente_id,
            Venda.sitvenda == "PAGA",
            ItVenda.tipoitem == "PRODUTO",
            ItVenda.produto_id == produto_id,
            ItVenda.sititvenda == "ATIVO",
            ItVenda.dtcriacao >= agora - timedelta(days=JANELA_DESCONTO_DIAS),
            BeneficioProdutoResgate.percentual_desconto > 0,
            BeneficioProdutoResgate.percentual_desconto < 100,
        )
        .first()
        is not None
    )


def _texto_tempo_restante(data_final: datetime, agora: datetime) -> str:
    segundos = max(0, int((data_final - agora).total_seconds()))
    horas, restante = divmod(segundos, 3600)
    minutos, segundos = divmod(restante, 60)
    return f"{horas:02}h {minutos:02}min {segundos:02}s"


def _validar_escopo(db: Session, dados: CampanhaIn, usuario: dict) -> None:
    loja = db.query(Loja).filter(Loja.loja_id == dados.loja_id, Loja.organizacao_id == dados.organizacao_id).first()
    produto = db.query(Produto).filter(Produto.produto_id == dados.produto_id, Produto.organizacao_id == dados.organizacao_id, Produto.sitproduto == "ATIVO").first()
    if not loja or not produto:
        raise HTTPException(404, "Loja ou produto não encontrado.")
    validar_mutacao_loja(usuario, dados.organizacao_id, dados.loja_id)


@router.get("/lojas/{loja_id}")
def listar_campanhas(loja_id: int, organizacao_id: int, usuario: dict = Depends(get_usuario_logado), db: Session = Depends(get_db)):
    validar_mutacao_loja(usuario, organizacao_id, loja_id)
    itens = db.query(BeneficioProdutoCampanha).filter(
        BeneficioProdutoCampanha.loja_id == loja_id,
        BeneficioProdutoCampanha.organizacao_id == organizacao_id,
        BeneficioProdutoCampanha.situacao == "ATIVA",
    ).order_by(BeneficioProdutoCampanha.dthrinicio.desc()).all()
    produtos = {int(p.produto_id): p.nmproduto for p in db.query(Produto).filter(Produto.produto_id.in_([i.produto_id for i in itens] or [-1])).all()}
    return [
        _campanha_out(
            i,
            resgates=(
                _total_pacotes_vendidos(db, i)
                if i.tipo == "PACOTE"
                else _total_unidades_promocionais(db, i)
                if i.tipo == "PERCENTUAL"
                else _total_roletas_utilizadas(db, int(i.beneficioprodutocampanha_id))
                if i.tipo == "ROLETA"
                else _total_resgates_validos(db, int(i.beneficioprodutocampanha_id))
            ),
            nmproduto=produtos.get(int(i.produto_id), "Produto"),
        )
        for i in itens
    ]


@router.post("", status_code=status.HTTP_201_CREATED)
def criar_campanha(dados: CampanhaIn, usuario: dict = Depends(get_usuario_logado), db: Session = Depends(get_db)):
    _validar_escopo(db, dados, usuario)
    _validar_nao_sobrepoe_campanha(db, dados)
    item = BeneficioProdutoCampanha(**dados.model_dump())
    db.add(item); db.commit(); db.refresh(item)
    return _campanha_out(item, resgates=0)


@router.put("/{campanha_id}")
def editar_campanha(campanha_id: int, dados: CampanhaIn, usuario: dict = Depends(get_usuario_logado), db: Session = Depends(get_db)):
    item = db.query(BeneficioProdutoCampanha).filter(BeneficioProdutoCampanha.beneficioprodutocampanha_id == campanha_id).first()
    if not item: raise HTTPException(404, "Campanha não encontrada.")
    _validar_escopo(db, dados, usuario)
    _validar_nao_sobrepoe_campanha(
        db,
        dados,
        campanha_id_atual=campanha_id,
    )
    for chave, valor in dados.model_dump().items(): setattr(item, chave, valor)
    db.commit(); db.refresh(item)
    return _campanha_out(item)


@router.delete("/{campanha_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_campanha(campanha_id: int, usuario: dict = Depends(get_usuario_logado), db: Session = Depends(get_db)):
    item = db.query(BeneficioProdutoCampanha).filter(BeneficioProdutoCampanha.beneficioprodutocampanha_id == campanha_id).first()
    if not item: raise HTTPException(404, "Campanha não encontrada.")
    validar_mutacao_loja(usuario, int(item.organizacao_id), int(item.loja_id))
    if db.query(BeneficioProdutoResgate.beneficioprodutoresgate_id).filter(BeneficioProdutoResgate.campanha_id == campanha_id).first():
        item.situacao = "INATIVA"
        db.commit()
        return
    db.delete(item); db.commit()


@router.get("/lojas/{loja_id}/ofertas")
def ofertas_ativas(
    loja_id: int,
    cliente_id: int | None = None,
    usuario: dict | None = Depends(get_usuario_opcional),
    db: Session = Depends(get_db),
):
    # As ofertas são públicas para que visitantes também as conheçam. A sessão
    # só é necessária para indicar se o próprio cliente já possui a cortesia.
    if cliente_id is not None:
        if usuario is None:
            raise HTTPException(status_code=403, detail="Não autenticado")
        exigir_cliente_autenticado(usuario, cliente_id)
    agora = _agora()
    itens = db.query(BeneficioProdutoCampanha).filter(
        BeneficioProdutoCampanha.loja_id == loja_id,
        BeneficioProdutoCampanha.situacao == "ATIVA",
        BeneficioProdutoCampanha.tipo.in_(("CORTESIA", "PERCENTUAL", "PACOTE", "ROLETA")),
        BeneficioProdutoCampanha.dthrinicio <= agora,
        or_(
            BeneficioProdutoCampanha.dthrfim.is_(None),
            BeneficioProdutoCampanha.dthrfim >= agora,
        ),
    ).all()
    retorno = []
    for item in itens:
        usados = (
            _total_pacotes_vendidos(db, item)
            if item.tipo == "PACOTE"
            else _total_unidades_promocionais(db, item)
            if item.tipo == "PERCENTUAL"
            else _total_roletas_utilizadas(db, int(item.beneficioprodutocampanha_id))
            if item.tipo == "ROLETA"
            else _total_resgates_validos(db, int(item.beneficioprodutocampanha_id))
        )
        if item.qtlimite is not None and usados >= item.qtlimite: continue
        oferta = _campanha_out(item, resgates=usados)
        if item.tipo == "CORTESIA":
            cortesia_pendente = cliente_id is not None and _tem_cortesia_pendente(
                db,
                cliente_id=cliente_id,
                produto_id=int(item.produto_id),
            )
            oferta["disponivel_para_cliente"] = not cortesia_pendente
            if cortesia_pendente:
                oferta["motivo_indisponibilidade"] = (
                    "Você já possui uma cortesia válida deste produto aguardando retirada."
                )
        retorno.append(oferta)
    return retorno


@router.get("/carrinhos/{carrinho_id}/roletas")
def roletas_do_carrinho(carrinho_id: int, cliente_id: int,
                        usuario: dict = Depends(get_usuario_logado), db: Session = Depends(get_db)):
    exigir_cliente_autenticado(usuario, cliente_id)
    carrinho = db.query(Carrinho).filter(Carrinho.carrinho_id == carrinho_id,
        Carrinho.cliente_id == cliente_id, Carrinho.sitcarrinho == "ABERTO").first()
    if not carrinho:
        raise HTTPException(404, "Carrinho não encontrado ou já finalizado.")
    produtos = {int(item.produto_id) for item in db.query(ItCarrinho).filter(
        ItCarrinho.carrinho_id == carrinho_id).all()}
    if not produtos:
        return []
    campanhas = db.query(BeneficioProdutoCampanha).filter(
        BeneficioProdutoCampanha.loja_id == carrinho.loja_id,
        BeneficioProdutoCampanha.organizacao_id == carrinho.organizacao_id,
        BeneficioProdutoCampanha.tipo == "ROLETA",
        BeneficioProdutoCampanha.produto_id.in_(produtos)).all()
    agora = _agora()
    resultado = []
    vistos = set()
    for campanha in campanhas:
        produto_id = int(campanha.produto_id)
        premio = db.query(BeneficioProdutoResgate).filter(
            BeneficioProdutoResgate.carrinho_id == carrinho_id,
            BeneficioProdutoResgate.produto_id == produto_id).first()
        if premio is not None and premio.campanha_id != campanha.beneficioprodutocampanha_id:
            continue
        if not premio and (not _periodo_ativo(campanha, agora) or
            (campanha.qtlimite is not None and _total_roletas_utilizadas(db, int(campanha.beneficioprodutocampanha_id)) >= campanha.qtlimite)):
            continue
        if produto_id in vistos:
            continue
        produto = db.query(Produto).filter(Produto.produto_id == produto_id).first()
        resultado.append({"campanha_id": int(campanha.beneficioprodutocampanha_id),
            "produto_id": produto_id, "nome_produto": produto.nmproduto if produto else "Produto",
            "ja_girou": premio is not None,
            "percentual_desconto": float(premio.percentual_desconto) if premio else None})
        vistos.add(produto_id)
    return resultado


@router.post("/{campanha_id}/girar")
def girar_roleta(campanha_id: int, dados: GiroIn, usuario: dict = Depends(get_usuario_logado), db: Session = Depends(get_db)):
    exigir_cliente_autenticado(usuario, dados.cliente_id)
    if dados.carrinho_id is None:
        raise HTTPException(409, "A roleta agora é girada no carrinho. Atualize o aplicativo.")
    carrinho = (db.query(Carrinho).filter(Carrinho.carrinho_id == dados.carrinho_id,
        Carrinho.cliente_id == dados.cliente_id, Carrinho.sitcarrinho == "ABERTO")
        .with_for_update().first())
    if not carrinho:
        raise HTTPException(404, "Carrinho não encontrado ou já finalizado.")
    campanha = (db.query(BeneficioProdutoCampanha).filter(
        BeneficioProdutoCampanha.beneficioprodutocampanha_id == campanha_id,
        BeneficioProdutoCampanha.loja_id == carrinho.loja_id,
        BeneficioProdutoCampanha.organizacao_id == carrinho.organizacao_id,
        BeneficioProdutoCampanha.tipo == "ROLETA").with_for_update().first())
    if not campanha:
        raise HTTPException(409, "Esta roleta não está disponível agora.")
    itens = (db.query(ItCarrinho).filter(ItCarrinho.carrinho_id == carrinho.carrinho_id,
        ItCarrinho.produto_id == campanha.produto_id).with_for_update().all())
    if not itens:
        raise HTTPException(409, "Adicione o produto ao carrinho antes de girar.")
    premio = (db.query(BeneficioProdutoResgate).filter(
        BeneficioProdutoResgate.carrinho_id == carrinho.carrinho_id,
        BeneficioProdutoResgate.produto_id == campanha.produto_id).with_for_update().first())
    if not _periodo_ativo(campanha, _agora()):
        raise HTTPException(409, "Esta roleta não está disponível agora.")
    if premio is not None and (premio.campanha_id != campanha_id or premio.situacao != "DISPONIVEL"):
        raise HTTPException(409, "Este desconto não está disponível neste carrinho.")
    desconto = secrets.choice(PERCENTUAIS_ROLETA)
    if premio is None:
        premio = BeneficioProdutoResgate(campanha_id=campanha_id, cliente_id=dados.cliente_id,
            produto_id=campanha.produto_id, carrinho_id=carrinho.carrinho_id,
            percentual_desconto=desconto, situacao="DISPONIVEL", dtexpiracao=None)
        db.add(premio)
        db.flush()
    else:
        premio.percentual_desconto = desconto
    economia = 0.0
    aplicou = False
    for item in itens:
        if item.beneficioprodutoresgate_id not in (None, premio.beneficioprodutoresgate_id):
            raise HTTPException(409, "Este produto possui outro benefício no carrinho.")
        base = item.vrpreco_original if item.vrpreco_original is not None else item.vrunitario
        preco_oferta = item.vrunitario if item.beneficioprodutoresgate_id is None else base
        campanha_promocional_id = getattr(item, "beneficioprodutocampanha_id", None)
        if campanha_promocional_id:
            promocao = db.query(BeneficioProdutoCampanha).filter(
                BeneficioProdutoCampanha.beneficioprodutocampanha_id == campanha_promocional_id).first()
            if promocao and promocao.tipo == "PACOTE":
                preco_oferta = promocao.vrpacote
            elif promocao and promocao.tipo == "PERCENTUAL":
                preco_oferta, _ = melhor_preco_roleta(base, base, promocao.percentual_desconto)
        escolhido, usar = melhor_preco_roleta(base, preco_oferta, desconto)
        item.vrpreco_original = base
        item.vrunitario = escolhido
        item.beneficioprodutoresgate_id = premio.beneficioprodutoresgate_id if usar else None
        economia += float(preco_oferta) - float(escolhido)
        aplicou = aplicou or usar
    db.commit()
    return {"resgate_id": int(premio.beneficioprodutoresgate_id), "percentual_desconto": desconto,
            "aplicado": aplicou, "economia_adicional": round(economia, 2), "ja_girou": False}


@router.post("/{campanha_id}/premios/{resgate_id}/dispensar")
def dispensar_premio_roleta(campanha_id: int, resgate_id: int, dados: GiroIn,
                            usuario: dict = Depends(get_usuario_logado), db: Session = Depends(get_db)):
    exigir_cliente_autenticado(usuario, dados.cliente_id)
    resgate = (db.query(BeneficioProdutoResgate)
        .join(BeneficioProdutoCampanha, BeneficioProdutoCampanha.beneficioprodutocampanha_id == BeneficioProdutoResgate.campanha_id)
        .filter(BeneficioProdutoResgate.beneficioprodutoresgate_id == resgate_id,
                BeneficioProdutoResgate.campanha_id == campanha_id,
                BeneficioProdutoResgate.cliente_id == dados.cliente_id,
                BeneficioProdutoCampanha.tipo == "ROLETA")
        .with_for_update().first())
    if not resgate:
        raise HTTPException(404, "Prêmio não encontrado.")
    if resgate.situacao == "CANCELADO":
        return {"ok": True}
    if resgate.situacao != "DISPONIVEL":
        raise HTTPException(409, "Este prêmio já foi utilizado.")
    em_carrinho = (db.query(ItCarrinho.itcarrinho_id).join(Carrinho, Carrinho.carrinho_id == ItCarrinho.carrinho_id)
        .filter(ItCarrinho.beneficioprodutoresgate_id == resgate_id, Carrinho.sitcarrinho == "ABERTO").first())
    em_compra = (db.query(ItVenda.itvenda_id).join(Venda, Venda.venda_id == ItVenda.venda_id)
        .filter(ItVenda.beneficioprodutoresgate_id == resgate_id, ItVenda.sititvenda == "ATIVO",
                Venda.sitvenda.in_(("PENDENTE", "PAGA"))).first())
    if em_carrinho or em_compra:
        raise HTTPException(409, "Este prêmio já está em uso.")
    resgate.situacao = "CANCELADO"
    db.commit()
    return {"ok": True}


@router.post("/{campanha_id}/resgatar-cortesia")
def resgatar_cortesia(campanha_id: int, dados: GiroIn, usuario: dict = Depends(get_usuario_logado), db: Session = Depends(get_db)):
    """Coloca a cortesia diretamente na carteira, sem transformar o preço do cardápio em zero."""
    exigir_cliente_autenticado(usuario, dados.cliente_id)
    agora = _agora()
    campanha = db.query(BeneficioProdutoCampanha).filter(BeneficioProdutoCampanha.beneficioprodutocampanha_id == campanha_id).with_for_update().first()
    if (
        not campanha
        or campanha.tipo != "CORTESIA"
        or not _periodo_ativo(campanha, agora)
    ):
        raise HTTPException(409, "Esta cortesia não está disponível agora.")
    total = _total_resgates_validos(db, campanha_id)
    if campanha.qtlimite is not None and total >= campanha.qtlimite: raise HTTPException(409, "As cortesias desta campanha terminaram.")
    if _tem_cortesia_pendente(
        db, cliente_id=dados.cliente_id, produto_id=int(campanha.produto_id)
    ):
        raise HTTPException(409, "Você já possui uma cortesia válida deste produto aguardando retirada.")
    resgate = BeneficioProdutoResgate(campanha_id=campanha_id, cliente_id=dados.cliente_id, produto_id=campanha.produto_id, percentual_desconto=100, situacao="DISPONIVEL")
    db.add(resgate); db.flush()
    loja = db.query(Loja).filter(
        Loja.loja_id == campanha.loja_id,
        Loja.organizacao_id == campanha.organizacao_id,
    ).first()
    dias_validade = int(getattr(loja, "nrdiavalidade", 0) or 0) if loja else 0
    controla_validade = (
        (getattr(loja, "idvalidadeprod", "S") or "S").upper() == "S"
        if loja
        else True
    )
    data_expira = (
        agora.date() + timedelta(days=dias_validade)
        if controla_validade and dias_validade > 0
        else None
    )
    carrinho = Carrinho(organizacao_id=campanha.organizacao_id, loja_id=campanha.loja_id, cliente_id=dados.cliente_id, sitcarrinho="ABERTO")
    db.add(carrinho); db.flush()
    venda = Venda(loja_id=campanha.loja_id, organizacao_id=campanha.organizacao_id, cliente_id=dados.cliente_id, carrinho_id=carrinho.carrinho_id, tipovenda="PRODUTO", dsplataforma="OUTROS", sitvenda="PENDENTE", totalvenda=0)
    db.add(venda); db.flush()
    db.add(ItVenda(venda_id=venda.venda_id, tipoitem="PRODUTO", produto_id=campanha.produto_id, beneficioprodutoresgate_id=resgate.beneficioprodutoresgate_id, qtitvenda=1, vrunititvenda=0, identregaitvenda="NAO", qrtokenitvenda=gerar_token_qr(), dtexpiraitvenda=data_expira))
    # Cortesia não depende de gateway: é uma cobrança interna, já quitada e
    # de valor zero. Assim ela aparece corretamente na carteira e pode ser
    # cancelada sem consultar Asaas ou Mercado Pago.
    db.add(PagVenda(
        venda_id=venda.venda_id,
        dsmetodopag="CORTESIA",
        vrpagvenda=0,
        sitpagvenda="PAGO",
        idtransacaopagvenda=f"CORTESIA-{venda.venda_id}",
        dtconftranspagvenda=agora,
        reference_id=f"CORTESIA-{venda.venda_id}",
        provedor="CORTESIA",
    ))
    db.flush()
    # Não passa pela validação legada de cortesias do cardápio: esta campanha
    # tem vida própria e preserva o preço público do produto.
    venda.sitvenda = "PAGA"
    carrinho.sitcarrinho = "FECHADO"
    resgate.situacao = "USADO"
    resgate.venda_id = venda.venda_id
    db.commit()
    return {"ok": True, "venda_id": int(venda.venda_id), "mensagem": "Cortesia resgatada e disponível na sua carteira."}
