import re
import unicodedata

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import get_operador_logado, get_usuario_logado
from app.database import get_db
from app.models.cliente import Cliente
from app.models.coraduvida import CoraDuvida
from app.models.coramensagem import CoraMensagem


router = APIRouter(prefix="/cora", tags=["Cora"])


class MensagemIn(BaseModel):
    mensagem: str = Field(min_length=1, max_length=3000)


class DuvidaIn(BaseModel):
    pergunta: str = Field(min_length=3, max_length=255)
    resposta: str = Field(min_length=3, max_length=5000)
    idordem: int = Field(default=1, ge=1)
    sitduvida: str = Field(default="ATIVA", max_length=15)


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


def _serializar_duvida(item: CoraDuvida) -> dict:
    return {
        "coraduvida_id": item.coraduvida_id,
        "pergunta": item.pergunta,
        "resposta": item.resposta,
        "idordem": item.idordem,
        "sitduvida": item.sitduvida,
    }


def _validar_duvida(dados: DuvidaIn) -> tuple[str, str, str]:
    pergunta = " ".join(dados.pergunta.split())
    resposta = dados.resposta.strip()
    situacao = dados.sitduvida.strip().upper()
    if situacao not in {"ATIVA", "INATIVA"}:
        raise HTTPException(422, "A situação deve ser ATIVA ou INATIVA.")
    return pergunta, resposta, situacao


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
    if duvida:
        pergunta.lida = "S"
    db.add_all([pergunta, retorno])
    db.commit()
    db.refresh(pergunta)
    db.refresh(retorno)
    return {"mensagens": [_serializar(pergunta), _serializar(retorno)]}


@router.get("/admin/duvidas")
def admin_listar_duvidas(
    _: dict = Depends(get_operador_logado), db: Session = Depends(get_db)
):
    itens = db.query(CoraDuvida).order_by(CoraDuvida.idordem, CoraDuvida.pergunta).all()
    return [_serializar_duvida(item) for item in itens]


@router.post("/admin/duvidas", status_code=201)
def admin_criar_duvida(
    dados: DuvidaIn,
    _: dict = Depends(get_operador_logado),
    db: Session = Depends(get_db),
):
    pergunta, resposta, situacao = _validar_duvida(dados)
    if db.query(CoraDuvida).filter(CoraDuvida.pergunta == pergunta).first():
        raise HTTPException(409, "Já existe uma dúvida com essa pergunta.")
    item = CoraDuvida(
        pergunta=pergunta,
        resposta=resposta,
        idordem=dados.idordem,
        sitduvida=situacao,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serializar_duvida(item)


@router.put("/admin/duvidas/{duvida_id}")
def admin_atualizar_duvida(
    duvida_id: int,
    dados: DuvidaIn,
    _: dict = Depends(get_operador_logado),
    db: Session = Depends(get_db),
):
    item = db.get(CoraDuvida, duvida_id)
    if not item:
        raise HTTPException(404, "Dúvida não encontrada.")
    pergunta, resposta, situacao = _validar_duvida(dados)
    duplicada = db.query(CoraDuvida).filter(
        CoraDuvida.pergunta == pergunta, CoraDuvida.coraduvida_id != duvida_id
    ).first()
    if duplicada:
        raise HTTPException(409, "Já existe uma dúvida com essa pergunta.")
    item.pergunta = pergunta
    item.resposta = resposta
    item.idordem = dados.idordem
    item.sitduvida = situacao
    db.commit()
    db.refresh(item)
    return _serializar_duvida(item)


@router.delete("/admin/duvidas/{duvida_id}", status_code=204)
def admin_excluir_duvida(
    duvida_id: int,
    _: dict = Depends(get_operador_logado),
    db: Session = Depends(get_db),
):
    item = db.get(CoraDuvida, duvida_id)
    if not item:
        raise HTTPException(404, "Dúvida não encontrada.")
    db.delete(item)
    db.commit()


@router.get("/admin/atendimentos")
def admin_listar_atendimentos(
    _: dict = Depends(get_operador_logado), db: Session = Depends(get_db)
):
    clientes = (
        db.query(Cliente)
        .join(CoraMensagem, CoraMensagem.cliente_id == Cliente.cliente_id)
        .group_by(Cliente.cliente_id)
        .order_by(func.max(CoraMensagem.dtcriacao).desc())
        .all()
    )
    retorno = []
    for cliente in clientes:
        ultima = db.query(CoraMensagem).filter(
            CoraMensagem.cliente_id == cliente.cliente_id
        ).order_by(CoraMensagem.dtcriacao.desc(), CoraMensagem.coramensagem_id.desc()).first()
        pendentes = db.query(CoraMensagem).filter(
            CoraMensagem.cliente_id == cliente.cliente_id,
            CoraMensagem.origem == "CLIENTE",
            CoraMensagem.lida == "N",
        ).count()
        retorno.append({
            "cliente_id": cliente.cliente_id,
            "nmcliente": cliente.nmcliente,
            "emailcliente": cliente.emailcliente,
            "ultima_mensagem": ultima.mensagem if ultima else "",
            "dtultima_mensagem": ultima.dtcriacao if ultima else None,
            "pendentes": pendentes,
        })
    return retorno


@router.get("/admin/atendimentos/{cliente_id}")
def admin_consultar_atendimento(
    cliente_id: int,
    _: dict = Depends(get_operador_logado),
    db: Session = Depends(get_db),
):
    cliente = db.get(Cliente, cliente_id)
    if not cliente:
        raise HTTPException(404, "Cliente não encontrado.")
    mensagens = db.query(CoraMensagem).filter(
        CoraMensagem.cliente_id == cliente_id
    ).order_by(CoraMensagem.dtcriacao, CoraMensagem.coramensagem_id).all()
    return {
        "cliente_id": cliente.cliente_id,
        "nmcliente": cliente.nmcliente,
        "emailcliente": cliente.emailcliente,
        "mensagens": [_serializar(item) for item in mensagens],
    }


@router.post("/admin/atendimentos/{cliente_id}/mensagens", status_code=201)
def admin_responder_atendimento(
    cliente_id: int,
    dados: MensagemIn,
    _: dict = Depends(get_operador_logado),
    db: Session = Depends(get_db),
):
    if not db.get(Cliente, cliente_id):
        raise HTTPException(404, "Cliente não encontrado.")
    db.query(CoraMensagem).filter(
        CoraMensagem.cliente_id == cliente_id,
        CoraMensagem.origem == "CLIENTE",
        CoraMensagem.lida == "N",
    ).update({CoraMensagem.lida: "S"}, synchronize_session=False)
    resposta = CoraMensagem(
        cliente_id=cliente_id,
        origem="CORA",
        mensagem=dados.mensagem.strip(),
        lida="N",
    )
    db.add(resposta)
    db.commit()
    db.refresh(resposta)
    return _serializar(resposta)
