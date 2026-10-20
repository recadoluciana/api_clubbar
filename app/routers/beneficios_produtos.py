from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.cliente_auth import exigir_cliente_autenticado
from app.core.permissoes_loja import validar_mutacao_loja
from app.core.security import get_usuario_logado
from app.database import get_db
from app.models.beneficio_produto import BeneficioProdutoCampanha, BeneficioProdutoResgate
from app.models.loja import Loja
from app.models.produto import Produto
from app.models.carrinho import Carrinho
from app.models.venda import Venda
from app.models.itvenda import ItVenda
from app.models.pagvenda import PagVenda
from app.services.venda_service import gerar_token_qr
from app.services.pagamento_status_service import set_venda_como_paga
from app.utils.datetime_utils import FUSO_BRASIL

router = APIRouter(prefix="/beneficios-produtos", tags=["Benefícios de produtos"])
# Promoção atual: os prêmios da roleta são sorteados apenas entre 10% e 20%.
PERCENTUAIS_ROLETA = (10, 20)
MAX_GIROS_POR_PRODUTO_EM_24H = 2
JANELA_GIRO_HORAS = 24
JANELA_DESCONTO_DIAS = 10


def _agora() -> datetime:
    return datetime.now(FUSO_BRASIL).replace(tzinfo=None)


class CampanhaIn(BaseModel):
    organizacao_id: int
    loja_id: int
    produto_id: int
    tipo: str = Field(pattern="^(CORTESIA|ROLETA|PACOTE)$")
    nmcampanha: str = Field(min_length=2, max_length=120)
    dthrinicio: datetime
    dthrfim: datetime
    qtlimite: int | None = Field(default=None, ge=1)
    limite_cliente_dia: int = Field(default=1, ge=1, le=10)
    qtitenspacote: int | None = Field(default=None, ge=2, le=99)
    vrpacote: Decimal | None = Field(
        default=None, gt=0, max_digits=10, decimal_places=2,
    )
    situacao: str = Field(default="ATIVA", pattern="^(ATIVA|INATIVA)$")

    @model_validator(mode="after")
    def periodo_valido(self):
        if self.dthrfim <= self.dthrinicio:
            raise ValueError("O fim da campanha deve ser posterior ao início.")
        if self.tipo == "PACOTE":
            if self.qtitenspacote is None or self.vrpacote is None:
                raise ValueError("Informe a quantidade e o preço da promoção em pacote.")
        else:
            self.qtitenspacote = None
            self.vrpacote = None
        return self


class GiroIn(BaseModel):
    cliente_id: int


def _campanha_out(item: BeneficioProdutoCampanha, *, resgates: int | None = None, nmproduto: str | None = None) -> dict:
    dados = {
        "campanha_id": int(item.beneficioprodutocampanha_id),
        "organizacao_id": int(item.organizacao_id), "loja_id": int(item.loja_id),
        "produto_id": int(item.produto_id), "tipo": item.tipo, "nmcampanha": item.nmcampanha,
        "dthrinicio": item.dthrinicio, "dthrfim": item.dthrfim, "qtlimite": item.qtlimite,
        "limite_cliente_dia": int(item.limite_cliente_dia or 1), "situacao": item.situacao,
        "qtitenspacote": int(item.qtitenspacote) if item.qtitenspacote else None,
        "vrpacote": float(item.vrpacote) if item.vrpacote is not None else None,
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


def _proxima_rodada_roleta(giros: list, agora: datetime) -> datetime | None:
    """Retorna a liberação após o segundo giro feito dentro de 24 horas."""
    if len(giros) < MAX_GIROS_POR_PRODUTO_EM_24H:
        return None
    ultimo_giro, penultimo_giro = giros[:MAX_GIROS_POR_PRODUTO_EM_24H]
    proxima_rodada = ultimo_giro.dtresgate + timedelta(hours=JANELA_GIRO_HORAS)
    if penultimo_giro.dtresgate < ultimo_giro.dtresgate - timedelta(
        hours=JANELA_GIRO_HORAS
    ):
        return None
    return proxima_rodada if agora < proxima_rodada else None


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
                else _total_resgates_validos(db, int(i.beneficioprodutocampanha_id))
            ),
            nmproduto=produtos.get(int(i.produto_id), "Produto"),
        )
        for i in itens
    ]


@router.post("", status_code=status.HTTP_201_CREATED)
def criar_campanha(dados: CampanhaIn, usuario: dict = Depends(get_usuario_logado), db: Session = Depends(get_db)):
    _validar_escopo(db, dados, usuario)
    item = BeneficioProdutoCampanha(**dados.model_dump())
    db.add(item); db.commit(); db.refresh(item)
    return _campanha_out(item, resgates=0)


@router.put("/{campanha_id}")
def editar_campanha(campanha_id: int, dados: CampanhaIn, usuario: dict = Depends(get_usuario_logado), db: Session = Depends(get_db)):
    item = db.query(BeneficioProdutoCampanha).filter(BeneficioProdutoCampanha.beneficioprodutocampanha_id == campanha_id).first()
    if not item: raise HTTPException(404, "Campanha não encontrada.")
    _validar_escopo(db, dados, usuario)
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
def ofertas_ativas(loja_id: int, cliente_id: int, usuario: dict = Depends(get_usuario_logado), db: Session = Depends(get_db)):
    exigir_cliente_autenticado(usuario, cliente_id)
    agora = _agora()
    itens = db.query(BeneficioProdutoCampanha).filter(BeneficioProdutoCampanha.loja_id == loja_id, BeneficioProdutoCampanha.situacao == "ATIVA", BeneficioProdutoCampanha.dthrinicio <= agora, BeneficioProdutoCampanha.dthrfim >= agora).all()
    retorno = []
    for item in itens:
        usados = (
            _total_pacotes_vendidos(db, item)
            if item.tipo == "PACOTE"
            else _total_resgates_validos(db, int(item.beneficioprodutocampanha_id))
        )
        if item.qtlimite is not None and usados >= item.qtlimite: continue
        oferta = _campanha_out(item, resgates=usados)
        if item.tipo == "CORTESIA":
            cortesia_pendente = _tem_cortesia_pendente(
                db,
                cliente_id=cliente_id,
                produto_id=int(item.produto_id),
            )
            oferta["disponivel_para_cliente"] = not cortesia_pendente
            if cortesia_pendente:
                oferta["motivo_indisponibilidade"] = (
                    "Você já possui uma cortesia válida deste produto aguardando retirada."
                )
        elif item.tipo == "ROLETA":
            ultimos_giros = (
                db.query(BeneficioProdutoResgate)
                .join(
                    BeneficioProdutoCampanha,
                    BeneficioProdutoCampanha.beneficioprodutocampanha_id
                    == BeneficioProdutoResgate.campanha_id,
                )
                .filter(
                    BeneficioProdutoResgate.cliente_id == cliente_id,
                    BeneficioProdutoResgate.produto_id == item.produto_id,
                    BeneficioProdutoCampanha.tipo == "ROLETA",
                )
                .order_by(BeneficioProdutoResgate.dtresgate.desc())
                .limit(MAX_GIROS_POR_PRODUTO_EM_24H)
                .all()
            )
            proxima_rodada = _proxima_rodada_roleta(ultimos_giros, agora)
            oferta["proxima_rodada_em"] = (
                proxima_rodada.isoformat() if proxima_rodada else None
            )
        retorno.append(oferta)
    return retorno


@router.post("/{campanha_id}/girar")
def girar_roleta(campanha_id: int, dados: GiroIn, usuario: dict = Depends(get_usuario_logado), db: Session = Depends(get_db)):
    exigir_cliente_autenticado(usuario, dados.cliente_id)
    agora = _agora()
    campanha = db.query(BeneficioProdutoCampanha).filter(BeneficioProdutoCampanha.beneficioprodutocampanha_id == campanha_id).with_for_update().first()
    if not campanha or campanha.tipo != "ROLETA" or campanha.situacao != "ATIVA" or not (campanha.dthrinicio <= agora <= campanha.dthrfim):
        raise HTTPException(409, "Esta roleta não está disponível agora.")
    if _tem_cortesia_pendente(
        db, cliente_id=dados.cliente_id, produto_id=int(campanha.produto_id)
    ):
        raise HTTPException(
            409,
            "Você possui uma cortesia deste produto aguardando retirada.",
        )
    if _tem_desconto_recente(
        db,
        cliente_id=dados.cliente_id,
        produto_id=int(campanha.produto_id),
        agora=agora,
    ):
        raise HTTPException(
            409,
            "Este produto já recebeu desconto para você nos últimos 10 dias.",
        )

    inicio_janela = agora - timedelta(hours=JANELA_GIRO_HORAS)
    giros_recentes = (
        db.query(BeneficioProdutoResgate)
        .join(
            BeneficioProdutoCampanha,
            BeneficioProdutoCampanha.beneficioprodutocampanha_id
            == BeneficioProdutoResgate.campanha_id,
        )
        .filter(
            BeneficioProdutoResgate.cliente_id == dados.cliente_id,
            BeneficioProdutoResgate.produto_id == campanha.produto_id,
            BeneficioProdutoResgate.dtresgate >= inicio_janela,
            BeneficioProdutoCampanha.tipo == "ROLETA",
        )
        .with_for_update()
        .all()
    )
    # Depois do segundo giro, a nova tentativa só é liberada 24 horas após
    # esse último giro (e não 24 horas após o primeiro).
    ultimos_dois_giros = (
        db.query(BeneficioProdutoResgate)
        .join(
            BeneficioProdutoCampanha,
            BeneficioProdutoCampanha.beneficioprodutocampanha_id
            == BeneficioProdutoResgate.campanha_id,
        )
        .filter(
            BeneficioProdutoResgate.cliente_id == dados.cliente_id,
            BeneficioProdutoResgate.produto_id == campanha.produto_id,
            BeneficioProdutoCampanha.tipo == "ROLETA",
        )
        .order_by(BeneficioProdutoResgate.dtresgate.desc())
        .limit(MAX_GIROS_POR_PRODUTO_EM_24H)
        .all()
    )
    proxima_rodada = _proxima_rodada_roleta(ultimos_dois_giros, agora)
    if proxima_rodada:
        raise HTTPException(
            409,
            "Você já usou suas duas tentativas para este produto. "
            f"Próxima rodada em {_texto_tempo_restante(proxima_rodada, agora)}.",
        )

    # O segundo giro substitui o prêmio ainda disponível do primeiro. Assim,
    # não ficam dois descontos pendentes para o mesmo produto.
    if giros_recentes:
        for giro in giros_recentes:
            if giro.situacao == "DISPONIVEL":
                giro.situacao = "CANCELADO"

    total = _total_resgates_validos(db, campanha_id)
    if campanha.qtlimite is not None and total >= campanha.qtlimite: raise HTTPException(409, "Esta promoção já atingiu o limite.")
    percentual = secrets.choice(PERCENTUAIS_ROLETA)
    resgate = BeneficioProdutoResgate(campanha_id=campanha_id, cliente_id=dados.cliente_id, produto_id=campanha.produto_id, percentual_desconto=percentual, situacao="DISPONIVEL", dtexpiracao=agora + timedelta(minutes=20))
    db.add(resgate); db.commit(); db.refresh(resgate)
    return {"resgate_id": int(resgate.beneficioprodutoresgate_id), "percentual_desconto": percentual, "expira_em": resgate.dtexpiracao, "mensagem": f"Você ganhou {percentual}% de desconto!" if percentual else "Desta vez não houve desconto. Você pode tentar novamente!"}


@router.post("/{campanha_id}/resgatar-cortesia")
def resgatar_cortesia(campanha_id: int, dados: GiroIn, usuario: dict = Depends(get_usuario_logado), db: Session = Depends(get_db)):
    """Coloca a cortesia diretamente na carteira, sem transformar o preço do cardápio em zero."""
    exigir_cliente_autenticado(usuario, dados.cliente_id)
    agora = _agora()
    campanha = db.query(BeneficioProdutoCampanha).filter(BeneficioProdutoCampanha.beneficioprodutocampanha_id == campanha_id).with_for_update().first()
    if not campanha or campanha.tipo != "CORTESIA" or campanha.situacao != "ATIVA" or not (campanha.dthrinicio <= agora <= campanha.dthrfim):
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
    db.add(PagVenda(venda_id=venda.venda_id, dsmetodopag="CORTESIA", vrpagvenda=0, sitpagvenda="PENDENTE", reference_id=f"CORTESIA-{venda.venda_id}", provedor="CORTESIA"))
    db.flush()
    # Não passa pela validação legada de cortesias do cardápio: esta campanha
    # tem vida própria e preserva o preço público do produto.
    venda.sitvenda = "PAGA"
    carrinho.sitcarrinho = "FECHADO"
    resgate.situacao = "USADO"
    resgate.venda_id = venda.venda_id
    db.commit()
    return {"ok": True, "venda_id": int(venda.venda_id), "mensagem": "Cortesia resgatada e disponível na sua carteira."}
