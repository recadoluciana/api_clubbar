import re
import unicodedata

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import get_usuario_logado
from app.database import get_db
from app.models.cliente import Cliente
from app.models.coraduvida import CoraDuvida
from app.models.coramensagem import CoraMensagem


router = APIRouter(prefix="/cora", tags=["Cora"])


class MensagemIn(BaseModel):
    mensagem: str = Field(min_length=1, max_length=3000)


def _cliente_logado(payload: dict, db: Session) -> Cliente:
    if payload.get("role") != "cliente":
        raise HTTPException(status_code=403, detail="Acesso exclusivo de cliente")
    try:
        cliente_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Cliente inválido")
    cliente = db.query(Cliente).filter(Cliente.cliente_id == cliente_id).first()
    if not cliente or cliente.sitcliente != "ATIVO":
        raise HTTPException(status_code=403, detail="Cliente inativo ou não encontrado")
    return cliente


def _serializar(item: CoraMensagem) -> dict:
    return {
        "coramensagem_id": item.coramensagem_id,
        "coraduvida_id": item.coraduvida_id,
        "origem": item.origem.value if hasattr(item.origem, "value") else item.origem,
        "mensagem": item.mensagem,
        "lida": item.lida,
        "dtcriacao": item.dtcriacao,
    }


def _normalizar(texto: str) -> set[str]:
    texto = unicodedata.normalize("NFKD", texto.lower())
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    return {
        palavra
        for palavra in re.findall(r"[a-z0-9]+", texto)
        if len(palavra) > 2 and palavra not in {"como", "onde", "para", "uma", "dos", "das", "meu", "minha"}
    }


def _resposta_pronta(db: Session, mensagem: str) -> tuple[CoraDuvida | None, str]:
    palavras = _normalizar(mensagem)
    melhor = None
    melhor_pontuacao = 0
    for duvida in db.query(CoraDuvida).filter(CoraDuvida.sitduvida == "ATIVA").all():
        pergunta = _normalizar(duvida.pergunta)
        pontuacao = len(palavras & pergunta)
        if pontuacao > melhor_pontuacao:
            melhor = duvida
            melhor_pontuacao = pontuacao
    if melhor and melhor_pontuacao >= 1:
        return melhor, melhor.resposta
    return None, (
        "Recebi sua mensagem. Se a resposta não estiver nas dúvidas frequentes, "
        "o atendimento Clubbar poderá acompanhar sua solicitação."
    )


@router.get("/duvidas")
def listar_duvidas(db: Session = Depends(get_db)):
    itens = (
        db.query(CoraDuvida)
        .filter(CoraDuvida.sitduvida == "ATIVA")
        .order_by(CoraDuvida.idordem, CoraDuvida.pergunta)
        .all()
    )
    return [
        {"coraduvida_id": x.coraduvida_id, "pergunta": x.pergunta, "resposta": x.resposta}
        for x in itens
    ]


@router.get("/mensagens")
def listar_mensagens(
    payload: dict = Depends(get_usuario_logado), db: Session = Depends(get_db)
):
    cliente = _cliente_logado(payload, db)
    mensagens = (
        db.query(CoraMensagem)
        .filter(CoraMensagem.cliente_id == cliente.cliente_id)
        .order_by(CoraMensagem.dtcriacao, CoraMensagem.coramensagem_id)
        .all()
    )
    if not mensagens:
        saudacao = CoraMensagem(
            cliente_id=cliente.cliente_id,
            origem="CORA",
            mensagem="Olá! Eu sou a Cora. Como posso ajudar?",
            lida="S",
        )
        db.add(saudacao)
        db.commit()
        db.refresh(saudacao)
        mensagens = [saudacao]
    for item in mensagens:
        if item.origem == "CORA" and item.lida == "N":
            item.lida = "S"
    db.commit()
    return [_serializar(x) for x in mensagens]


@router.post("/mensagens", status_code=201)
def enviar_mensagem(
    dados: MensagemIn,
    payload: dict = Depends(get_usuario_logado),
    db: Session = Depends(get_db),
):
    cliente = _cliente_logado(payload, db)
    texto = dados.mensagem.strip()
    pergunta = CoraMensagem(
        cliente_id=cliente.cliente_id, origem="CLIENTE", mensagem=texto, lida="N"
    )
    duvida, resposta = _resposta_pronta(db, texto)
    retorno = CoraMensagem(
        cliente_id=cliente.cliente_id,
        coraduvida_id=duvida.coraduvida_id if duvida else None,
        origem="CORA",
        mensagem=resposta,
        lida="N",
    )
    db.add_all([pergunta, retorno])
    db.commit()
    db.refresh(pergunta)
    db.refresh(retorno)
    return {"mensagens": [_serializar(pergunta), _serializar(retorno)]}
