from __future__ import annotations

import secrets
from datetime import datetime, timedelta

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
PERCENTUAIS_ROLETA = (10, 20, 0, 30, 50)


def _agora() -> datetime:
    return datetime.now(FUSO_BRASIL).replace(tzinfo=None)


class CampanhaIn(BaseModel):
    organizacao_id: int
    loja_id: int
    produto_id: int
    tipo: str = Field(pattern="^(CORTESIA|ROLETA)$")
    nmcampanha: str = Field(min_length=2, max_length=120)
    dthrinicio: datetime
    dthrfim: datetime
    qtlimite: int | None = Field(default=None, ge=1)
    limite_cliente_dia: int = Field(default=1, ge=1, le=10)
    situacao: str = Field(default="ATIVA", pattern="^(ATIVA|INATIVA)$")

    @model_validator(mode="after")
    def periodo_valido(self):
        if self.dthrfim <= self.dthrinicio:
            raise ValueError("O fim da campanha deve ser posterior ao início.")
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
    }
    if resgates is not None:
        dados["resgates"] = resgates
        dados["restantes"] = None if item.qtlimite is None else max(0, int(item.qtlimite) - resgates)
    if nmproduto is not None:
        dados["nmproduto"] = nmproduto
    return dados


def _validar_escopo(db: Session, dados: CampanhaIn, usuario: dict) -> None:
    loja = db.query(Loja).filter(Loja.loja_id == dados.loja_id, Loja.organizacao_id == dados.organizacao_id).first()
    produto = db.query(Produto).filter(Produto.produto_id == dados.produto_id, Produto.organizacao_id == dados.organizacao_id, Produto.sitproduto == "ATIVO").first()
    if not loja or not produto:
        raise HTTPException(404, "Loja ou produto não encontrado.")
    validar_mutacao_loja(usuario, dados.organizacao_id, dados.loja_id)


@router.get("/lojas/{loja_id}")
def listar_campanhas(loja_id: int, organizacao_id: int, usuario: dict = Depends(get_usuario_logado), db: Session = Depends(get_db)):
    validar_mutacao_loja(usuario, organizacao_id, loja_id)
    itens = db.query(BeneficioProdutoCampanha).filter(BeneficioProdutoCampanha.loja_id == loja_id, BeneficioProdutoCampanha.organizacao_id == organizacao_id).order_by(BeneficioProdutoCampanha.dthrinicio.desc()).all()
    produtos = {int(p.produto_id): p.nmproduto for p in db.query(Produto).filter(Produto.produto_id.in_([i.produto_id for i in itens] or [-1])).all()}
    return [_campanha_out(i, resgates=int(db.query(func.count(BeneficioProdutoResgate.beneficioprodutoresgate_id)).filter(BeneficioProdutoResgate.campanha_id == i.beneficioprodutocampanha_id).scalar() or 0), nmproduto=produtos.get(int(i.produto_id), "Produto")) for i in itens]


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
        usados = int(db.query(func.count(BeneficioProdutoResgate.beneficioprodutoresgate_id)).filter(BeneficioProdutoResgate.campanha_id == item.beneficioprodutocampanha_id).scalar() or 0)
        if item.qtlimite is not None and usados >= item.qtlimite: continue
        retorno.append(_campanha_out(item, resgates=usados))
    return retorno


@router.post("/{campanha_id}/girar")
def girar_roleta(campanha_id: int, dados: GiroIn, usuario: dict = Depends(get_usuario_logado), db: Session = Depends(get_db)):
    exigir_cliente_autenticado(usuario, dados.cliente_id)
    agora = _agora()
    campanha = db.query(BeneficioProdutoCampanha).filter(BeneficioProdutoCampanha.beneficioprodutocampanha_id == campanha_id).with_for_update().first()
    if not campanha or campanha.tipo != "ROLETA" or campanha.situacao != "ATIVA" or not (campanha.dthrinicio <= agora <= campanha.dthrfim):
        raise HTTPException(409, "Esta roleta não está disponível agora.")
    inicio_dia = agora.replace(hour=0, minute=0, second=0, microsecond=0)
    usados_cliente = int(db.query(func.count(BeneficioProdutoResgate.beneficioprodutoresgate_id)).filter(BeneficioProdutoResgate.campanha_id == campanha_id, BeneficioProdutoResgate.cliente_id == dados.cliente_id, BeneficioProdutoResgate.dtresgate >= inicio_dia).scalar() or 0)
    if usados_cliente >= int(campanha.limite_cliente_dia or 1): raise HTTPException(409, "Você já girou esta roleta hoje.")
    total = int(db.query(func.count(BeneficioProdutoResgate.beneficioprodutoresgate_id)).filter(BeneficioProdutoResgate.campanha_id == campanha_id).scalar() or 0)
    if campanha.qtlimite is not None and total >= campanha.qtlimite: raise HTTPException(409, "Esta promoção já atingiu o limite.")
    percentual = secrets.choice(PERCENTUAIS_ROLETA)
    resgate = BeneficioProdutoResgate(campanha_id=campanha_id, cliente_id=dados.cliente_id, produto_id=campanha.produto_id, percentual_desconto=percentual, situacao="DISPONIVEL", dtexpiracao=agora + timedelta(minutes=20))
    db.add(resgate); db.commit(); db.refresh(resgate)
    return {"resgate_id": int(resgate.beneficioprodutoresgate_id), "percentual_desconto": percentual, "expira_em": resgate.dtexpiracao, "mensagem": f"Você ganhou {percentual}% de desconto!" if percentual else "Desta vez não houve desconto. Tente novamente amanhã."}


@router.post("/{campanha_id}/resgatar-cortesia")
def resgatar_cortesia(campanha_id: int, dados: GiroIn, usuario: dict = Depends(get_usuario_logado), db: Session = Depends(get_db)):
    """Coloca a cortesia diretamente na carteira, sem transformar o preço do cardápio em zero."""
    exigir_cliente_autenticado(usuario, dados.cliente_id)
    agora = _agora()
    campanha = db.query(BeneficioProdutoCampanha).filter(BeneficioProdutoCampanha.beneficioprodutocampanha_id == campanha_id).with_for_update().first()
    if not campanha or campanha.tipo != "CORTESIA" or campanha.situacao != "ATIVA" or not (campanha.dthrinicio <= agora <= campanha.dthrfim):
        raise HTTPException(409, "Esta cortesia não está disponível agora.")
    total = int(db.query(func.count(BeneficioProdutoResgate.beneficioprodutoresgate_id)).filter(BeneficioProdutoResgate.campanha_id == campanha_id).scalar() or 0)
    if campanha.qtlimite is not None and total >= campanha.qtlimite: raise HTTPException(409, "As cortesias desta campanha terminaram.")
    pendente = db.query(BeneficioProdutoResgate).filter(BeneficioProdutoResgate.cliente_id == dados.cliente_id, BeneficioProdutoResgate.situacao == "DISPONIVEL", BeneficioProdutoResgate.percentual_desconto == 100).first()
    if pendente: raise HTTPException(409, "Você já possui uma cortesia aguardando retirada.")
    resgate = BeneficioProdutoResgate(campanha_id=campanha_id, cliente_id=dados.cliente_id, produto_id=campanha.produto_id, percentual_desconto=100, situacao="DISPONIVEL")
    db.add(resgate); db.flush()
    carrinho = Carrinho(organizacao_id=campanha.organizacao_id, loja_id=campanha.loja_id, cliente_id=dados.cliente_id, sitcarrinho="ABERTO")
    db.add(carrinho); db.flush()
    venda = Venda(loja_id=campanha.loja_id, organizacao_id=campanha.organizacao_id, cliente_id=dados.cliente_id, carrinho_id=carrinho.carrinho_id, tipovenda="PRODUTO", dsplataforma="OUTROS", sitvenda="PENDENTE", totalvenda=0)
    db.add(venda); db.flush()
    db.add(ItVenda(venda_id=venda.venda_id, tipoitem="PRODUTO", produto_id=campanha.produto_id, beneficioprodutoresgate_id=resgate.beneficioprodutoresgate_id, qtitvenda=1, vrunititvenda=0, identregaitvenda="NAO", qrtokenitvenda=gerar_token_qr()))
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
