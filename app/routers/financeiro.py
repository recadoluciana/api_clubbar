from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import get_operador_logado, get_usuario_logado
from app.core.permissoes_loja import validar_mutacao_loja
from app.database import get_db
from app.models.loja import Loja
from app.models.lojacontabancaria import LojaContaBancaria
from app.models.repassefinanceiro import RepasseFinanceiro
from app.models.venda import Venda


router = APIRouter(prefix="/financeiro", tags=["Financeiro"])


class ContaBancariaIn(BaseModel):
    codigobanco: str = Field(min_length=1, max_length=10)
    nmbanco: str | None = Field(default=None, max_length=100)
    agencia: str = Field(min_length=1, max_length=20)
    nrconta: str = Field(min_length=1, max_length=30)
    digitoconta: str | None = Field(default=None, max_length=5)
    tipoconta: str = Field(default="CORRENTE", max_length=20)
    nmtitular: str = Field(min_length=2, max_length=150)
    cpfcnpjtitular: str = Field(min_length=11, max_length=20)
    chavepix: str | None = Field(default=None, max_length=150)
    tipochavepix: str | None = Field(default=None, max_length=20)
    status: str = Field(default="ATIVA", max_length=15)


class RepasseUpdateIn(BaseModel):
    status: str = Field(max_length=20)
    dtprevista: date | None = None
    dtpagamento: datetime | None = None
    idtransferencia: str | None = Field(default=None, max_length=100)
    urlcomprovante: str | None = Field(default=None, max_length=500)
    observacao: str | None = None


def _loja_do_parceiro(db: Session, loja_id: int, usuario: dict) -> Loja:
    if usuario.get("role") != "usuario":
        raise HTTPException(status_code=403, detail="Acesso permitido ao parceiro")
    loja = db.query(Loja).filter(
        Loja.loja_id == loja_id,
        Loja.organizacao_id == int(usuario.get("organizacao_id") or 0),
    ).first()
    if not loja:
        raise HTTPException(status_code=404, detail="Loja não encontrada")
    validar_mutacao_loja(usuario, loja.organizacao_id, loja.loja_id)
    return loja


def _conta_saida(conta: LojaContaBancaria) -> dict:
    return {campo: getattr(conta, campo) for campo in (
        "lojacontabancaria_id", "organizacao_id", "loja_id", "codigobanco", "nmbanco",
        "agencia", "nrconta", "digitoconta", "tipoconta", "nmtitular", "cpfcnpjtitular",
        "chavepix", "tipochavepix", "status", "dtcriacao", "dtultatu",
    )}


def _repasse_saida(
    repasse: RepasseFinanceiro,
    nmloja: str | None = None,
    dtvenda: datetime | None = None,
) -> dict:
    return {
        "repassefinanceiro_id": repasse.repassefinanceiro_id,
        "organizacao_id": repasse.organizacao_id,
        "loja_id": repasse.loja_id,
        "nmloja": nmloja,
        "venda_id": repasse.venda_id,
        "dtvenda": dtvenda,
        "vrbruto": float(repasse.vrbruto or 0),
        "vrtaxaclubbar": float(repasse.vrtaxaclubbar or 0),
        "vrrepasse": float(repasse.vrrepasse or 0),
        "status": repasse.status,
        "dtprevista": repasse.dtprevista,
        "dtpagamento": repasse.dtpagamento,
        "idtransferencia": repasse.idtransferencia,
        "urlcomprovante": repasse.urlcomprovante,
        "observacao": repasse.observacao,
        "dtcriacao": repasse.dtcriacao,
    }


@router.get("/lojas/{loja_id}/conta-bancaria")
def consultar_conta_bancaria(loja_id: int, usuario: dict = Depends(get_usuario_logado), db: Session = Depends(get_db)):
    _loja_do_parceiro(db, loja_id, usuario)
    conta = db.query(LojaContaBancaria).filter(LojaContaBancaria.loja_id == loja_id).first()
    if not conta:
        raise HTTPException(status_code=404, detail="Conta bancária não cadastrada")
    return _conta_saida(conta)


@router.put("/lojas/{loja_id}/conta-bancaria")
def salvar_conta_bancaria(loja_id: int, payload: ContaBancariaIn, usuario: dict = Depends(get_usuario_logado), db: Session = Depends(get_db)):
    loja = _loja_do_parceiro(db, loja_id, usuario)
    conta = db.query(LojaContaBancaria).filter(LojaContaBancaria.loja_id == loja_id).first()
    if not conta:
        conta = LojaContaBancaria(loja_id=loja_id, organizacao_id=loja.organizacao_id)
        db.add(conta)
    for campo, valor in payload.model_dump().items():
        setattr(conta, campo, valor.strip() if isinstance(valor, str) else valor)
    conta.tipoconta = conta.tipoconta.upper()
    conta.status = conta.status.upper()
    if conta.status == "ATIVA":
        bloqueados = db.query(RepasseFinanceiro).filter(
            RepasseFinanceiro.loja_id == loja_id,
            RepasseFinanceiro.status == "BLOQUEADO",
        ).all()
        for repasse in bloqueados:
            for campo in ("codigobanco", "agencia", "nrconta", "digitoconta", "tipoconta", "nmtitular", "cpfcnpjtitular"):
                setattr(repasse, campo, getattr(conta, campo))
            repasse.status = "PENDENTE"
    db.commit()
    db.refresh(conta)
    return _conta_saida(conta)


@router.get("/repasses")
def listar_repasses(
    status: str | None = Query(default=None),
    loja_id: int | None = Query(default=None),
    _: dict = Depends(get_operador_logado),
    db: Session = Depends(get_db),
):
    query = db.query(RepasseFinanceiro, Loja.nmloja).join(Loja, Loja.loja_id == RepasseFinanceiro.loja_id)
    if status:
        query = query.filter(RepasseFinanceiro.status == status.upper())
    if loja_id:
        query = query.filter(RepasseFinanceiro.loja_id == loja_id)
    registros = query.order_by(RepasseFinanceiro.dtcriacao.desc()).limit(500).all()
    return [_repasse_saida(repasse, nmloja) for repasse, nmloja in registros]


@router.get("/parceiro/resumo")
def resumo_financeiro_parceiro(
    loja_id: int | None = Query(default=None),
    usuario: dict = Depends(get_usuario_logado),
    db: Session = Depends(get_db),
):
    if usuario.get("role") != "usuario":
        raise HTTPException(status_code=403, detail="Acesso permitido apenas ao parceiro")
    organizacao_id = int(usuario.get("organizacao_id") or 0)
    if organizacao_id <= 0:
        raise HTTPException(status_code=403, detail="Token sem organização válida")
    loja = None
    if loja_id is not None:
        loja = _loja_do_parceiro(db, loja_id, usuario)
    elif usuario.get("loja_id") is not None:
        loja_id = int(usuario["loja_id"])
        loja = _loja_do_parceiro(db, loja_id, usuario)

    filtros = [RepasseFinanceiro.organizacao_id == organizacao_id]
    if loja_id is not None:
        filtros.append(RepasseFinanceiro.loja_id == loja_id)

    totais = {status: 0.0 for status in ("BLOQUEADO", "PENDENTE", "AGENDADO", "PAGO", "CANCELADO")}
    linhas = db.query(
        RepasseFinanceiro.status,
        func.coalesce(func.sum(RepasseFinanceiro.vrrepasse), 0),
    ).filter(*filtros).group_by(RepasseFinanceiro.status).all()
    for status_repasse, total in linhas:
        totais[str(status_repasse).upper()] = float(total or 0)

    recentes = db.query(RepasseFinanceiro, Loja.nmloja, Venda.dtcriacao).join(
        Loja, Loja.loja_id == RepasseFinanceiro.loja_id
    ).join(
        Venda, Venda.venda_id == RepasseFinanceiro.venda_id
    ).filter(*filtros).order_by(RepasseFinanceiro.dtcriacao.desc()).limit(100).all()
    return {
        "nmloja": loja.nmloja if loja is not None else None,
        "totais": totais,
        "total_a_receber": totais["BLOQUEADO"] + totais["PENDENTE"] + totais["AGENDADO"],
        "total_recebido": totais["PAGO"],
        "repasses": [
            _repasse_saida(repasse, nmloja, dtvenda)
            for repasse, nmloja, dtvenda in recentes
        ],
    }


@router.patch("/repasses/{repasse_id}")
def atualizar_repasse(
    repasse_id: int,
    payload: RepasseUpdateIn,
    _: dict = Depends(get_operador_logado),
    db: Session = Depends(get_db),
):
    repasse = db.query(RepasseFinanceiro).filter(RepasseFinanceiro.repassefinanceiro_id == repasse_id).first()
    if not repasse:
        raise HTTPException(status_code=404, detail="Repasse não encontrado")
    novo_status = payload.status.upper()
    if novo_status not in {"BLOQUEADO", "PENDENTE", "AGENDADO", "PAGO", "CANCELADO"}:
        raise HTTPException(status_code=422, detail="Status de repasse inválido")
    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(repasse, campo, novo_status if campo == "status" else valor)
    if novo_status == "PAGO" and not repasse.dtpagamento:
        repasse.dtpagamento = datetime.now()
    db.commit()
    db.refresh(repasse)
    return repasse
