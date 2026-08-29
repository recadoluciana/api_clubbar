import re
import secrets
import traceback
import unicodedata
from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy import case
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.security import get_operador_logado
from app.core.security import hash_senha
from app.models.cidade import Cidade
from app.models.categoria import Categoria
from app.models.estado import Estado
from app.models.leadparceiro import LeadParceiro
from app.models.leadestabelecimento import LeadEstabelecimento
from app.schemas.leadparceiro import (
    LeadParceiroCreate,
    LeadParceiroOut,
    LeadParceiroCadastroOut,
    LeadParceiroUpdate,
    ConverterLeadParceiroIn,
    LeadEstabelecimentoCreate,
    LeadEstabelecimentoOut,
)

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.leadparceiro import LeadParceiro
from app.models.loja import Loja
from app.models.organizacao import Organizacao
from app.models.usuario import Usuario
from app.models.leadmensagem import LeadMensagem
from app.services.portal_acesso_service import criar_acesso_portal
from app.services.email_service import enviar_convite_parceiro


CATEGORIAS_PADRAO = (
    "Cervejas",
    "Drinks",
    "Destilados",
    "Bebidas sem álcool",
    "Porções",
    "Lanches",
    "Outros",
)


router = APIRouter(
    prefix="/parceiros",
    tags=["Parceiros"],
)


def _dias_espera(dtcriacao: datetime) -> int:
    diferenca = datetime.now() - dtcriacao

    return max(diferenca.days, 0)


def _serializar_lead(
    lead: LeadParceiro,
    estado: Estado,
    cidade: Cidade,
    ultima_origem_mensagem: str | None = None,
) -> dict:
    status_lead = (
        lead.status.value
        if hasattr(lead.status, "value")
        else str(lead.status)
    )

    return {
        "leadparceiro_id": lead.leadparceiro_id,
        "nmresponsavel": lead.nmresponsavel,
        "nmestabelecimento": lead.nmestabelecimento,
        "tipo": lead.tipo,
        "tipovenda": lead.tipovenda,
        "telefone": lead.telefone,
        "email": lead.email,
        "estado_id": lead.estado_id,
        "cidade_id": lead.cidade_id,
        "nmestado": estado.nmestado,
        "sgestado": estado.sgestado,
        "nmcidade": cidade.nmcidade,
        "mensagem": lead.mensagem,
        "status": status_lead,
        "dtcriacao": lead.dtcriacao,
        "dtultatu": lead.dtultatu,
        "dias_espera": _dias_espera(
            lead.dtcriacao,
        ),
        "aguardando_resposta": ultima_origem_mensagem == "LEAD",
        "estabelecimentos": [],
    }


def _serializar_estabelecimento(item: LeadEstabelecimento) -> dict:
    return {
        "leadestabelecimento_id": item.leadestabelecimento_id,
        "leadparceiro_id": item.leadparceiro_id,
        "nmestabelecimento": item.nmestabelecimento,
        "tipo": item.tipo,
        "tipovenda": item.tipovenda,
        "cpfcnpj": item.cpfcnpj,
        "estado_id": item.estado_id,
        "cidade_id": item.cidade_id,
        "mensagem": item.mensagem,
        "status": item.status.value if hasattr(item.status, "value") else item.status,
        "decisao": item.decisao,
        "vrtaxaprod": float(item.vrtaxaprod),
        "vrtaxaing": float(item.vrtaxaing),
        "dtcriacao": item.dtcriacao,
        "dtaceite": item.dtaceite,
        "dtconversao": item.dtconversao,
    }


def _carregar_estabelecimentos(db: Session, leadparceiro_id: int) -> list[dict]:
    itens = (
        db.query(LeadEstabelecimento)
        .filter(LeadEstabelecimento.leadparceiro_id == leadparceiro_id)
        .order_by(LeadEstabelecimento.leadestabelecimento_id.asc())
        .all()
    )
    return [_serializar_estabelecimento(item) for item in itens]


def _buscar_lead_com_localidade(
    db: Session,
    leadparceiro_id: int,
):
    return (
        db.query(
            LeadParceiro,
            Estado,
            Cidade,
        )
        .join(
            Estado,
            Estado.estado_id
            == LeadParceiro.estado_id,
        )
        .join(
            Cidade,
            Cidade.cidade_id
            == LeadParceiro.cidade_id,
        )
        .filter(
            LeadParceiro.leadparceiro_id
            == leadparceiro_id,
        )
        .first()
    )

@router.post(
    "/interesse",
    response_model=LeadParceiroCadastroOut,
    status_code=status.HTTP_201_CREATED,
)
def criar_interesse_parceiro(
    payload: LeadParceiroCreate,
    db: Session = Depends(get_db),
):
    estado = (
        db.query(Estado)
        .filter(
            Estado.estado_id == payload.estado_id,
        )
        .first()
    )

    if not estado:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Estado não encontrado.",
        )

    cidade = (
        db.query(Cidade)
        .filter(
            Cidade.cidade_id == payload.cidade_id,
        )
        .first()
    )

    if not cidade:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cidade não encontrada.",
        )

    if cidade.estado_id != payload.estado_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "A cidade informada não pertence "
                "ao estado selecionado."
            ),
        )

    lead = LeadParceiro(
        nmresponsavel=payload.nmresponsavel,
        nmestabelecimento=payload.nmestabelecimento,
        tipo=payload.tipo,
        tipovenda=payload.tipovenda,
        telefone=payload.telefone,
        email=payload.email,
        estado_id=payload.estado_id,
        cidade_id=payload.cidade_id,
        mensagem=payload.mensagem,
    )

    try:
        db.add(lead)

        # Gera o leadparceiro_id sem finalizar a transação.
        db.flush()

        estabelecimento = LeadEstabelecimento(
            leadparceiro_id=lead.leadparceiro_id,
            nmestabelecimento=payload.nmestabelecimento,
            tipo=payload.tipo,
            tipovenda=payload.tipovenda,
            estado_id=payload.estado_id,
            cidade_id=payload.cidade_id,
            mensagem=payload.mensagem,
        )
        db.add(estabelecimento)
        db.flush()

        acesso_portal = criar_acesso_portal(
            db=db,
            leadparceiro_id=lead.leadparceiro_id,
        )

        db.commit()
        db.refresh(lead)

        resposta = _serializar_lead(
            lead,
            estado,
            cidade,
        )

        resposta["acesso_portal"] = acesso_portal
        resposta["estabelecimentos"] = [
            _serializar_estabelecimento(estabelecimento)
        ]

        return resposta

    except Exception as erro:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao cadastrar interesse: {str(erro)}",
        ) from erro


@router.get(
    "",
    response_model=list[LeadParceiroOut],
)
def listar_interesses_parceiros(
    _: dict = Depends(get_operador_logado),
    db: Session = Depends(get_db),
):
    ultima_origem_mensagem = (
        db.query(LeadMensagem.origem)
        .filter(LeadMensagem.leadparceiro_id == LeadParceiro.leadparceiro_id)
        .order_by(
            LeadMensagem.dtcriacao.desc(),
            LeadMensagem.leadmensagem_id.desc(),
        )
        .limit(1)
        .correlate(LeadParceiro)
        .scalar_subquery()
    )

    prioridade_status = case(
        (LeadParceiro.status == "NOVO", 1),
        (LeadParceiro.status == "CONTATADO", 2),
        (LeadParceiro.status == "NEGOCIANDO", 3),
        (LeadParceiro.status == "ACEITOU_PARCERIA", 4),
        (LeadParceiro.status == "CONVERTIDO", 5),
        (LeadParceiro.status == "RECUSOU_PARCERIA", 6),
        else_=6,
    )

    resultados = (
        db.query(
            LeadParceiro,
            Estado,
            Cidade,
            ultima_origem_mensagem.label("ultima_origem_mensagem"),
        )
        .join(
            Estado,
            Estado.estado_id
            == LeadParceiro.estado_id,
        )
        .join(
            Cidade,
            Cidade.cidade_id
            == LeadParceiro.cidade_id,
        )
        .order_by(
            prioridade_status.asc(),
            LeadParceiro.dtcriacao.asc(),
        )
        .all()
    )

    resposta = []
    for lead, estado, cidade, origem in resultados:
        item = _serializar_lead(lead, estado, cidade, origem)
        item["estabelecimentos"] = _carregar_estabelecimentos(
            db, lead.leadparceiro_id
        )
        resposta.append(item)
    return resposta


@router.get(
    "/{leadparceiro_id}",
    response_model=LeadParceiroOut,
)
def buscar_interesse_parceiro(
    leadparceiro_id: int,
    _: dict = Depends(get_operador_logado),
    db: Session = Depends(get_db),
):
    resultado = _buscar_lead_com_localidade(
        db,
        leadparceiro_id,
    )

    if not resultado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead não encontrado.",
        )

    lead, estado, cidade = resultado

    resposta = _serializar_lead(
        lead,
        estado,
        cidade,
    )
    resposta["estabelecimentos"] = _carregar_estabelecimentos(
        db, lead.leadparceiro_id
    )
    return resposta


@router.post(
    "/{leadparceiro_id}/estabelecimentos",
    response_model=LeadEstabelecimentoOut,
    status_code=status.HTTP_201_CREATED,
)
def adicionar_estabelecimento(
    leadparceiro_id: int,
    payload: LeadEstabelecimentoCreate,
    _: dict = Depends(get_operador_logado),
    db: Session = Depends(get_db),
):
    lead = (
        db.query(LeadParceiro)
        .filter(LeadParceiro.leadparceiro_id == leadparceiro_id)
        .first()
    )
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado.")
    cidade = db.query(Cidade).filter(Cidade.cidade_id == payload.cidade_id).first()
    if not cidade or cidade.estado_id != payload.estado_id:
        raise HTTPException(
            status_code=422,
            detail="Cidade e estado informados são incompatíveis.",
        )
    item = LeadEstabelecimento(
        leadparceiro_id=leadparceiro_id,
        **payload.model_dump(),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serializar_estabelecimento(item)


@router.put(
    "/{leadparceiro_id}",
    response_model=LeadParceiroOut,
)
def atualizar_interesse_parceiro(
    leadparceiro_id: int,
    payload: LeadParceiroUpdate,
    _: dict = Depends(get_operador_logado),
    db: Session = Depends(get_db),
):
    lead = (
        db.query(LeadParceiro)
        .filter(
            LeadParceiro.leadparceiro_id
            == leadparceiro_id,
        )
        .first()
    )

    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead não encontrado.",
        )

    if payload.nmresponsavel is not None:
        lead.nmresponsavel = (
            payload.nmresponsavel
        )

    if payload.tipo is not None:
        lead.tipo = payload.tipo

    if payload.tipovenda is not None:
        lead.tipovenda = payload.tipovenda

    if payload.telefone is not None:
        lead.telefone = payload.telefone

    if payload.email is not None:
        lead.email = payload.email

    if payload.status is not None:
        lead.status = payload.status

    db.commit()
    db.refresh(lead)

    resultado = _buscar_lead_com_localidade(
        db,
        leadparceiro_id,
    )

    if not resultado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead não encontrado após atualização.",
        )

    lead_atualizado, estado, cidade = resultado

    return _serializar_lead(
        lead_atualizado,
        estado,
        cidade,
    )

def _somente_numeros(valor: str) -> str:
    return re.sub(r"\D", "", valor or "")


def _normalizar_texto(valor: str) -> str:
    texto = unicodedata.normalize(
        "NFD",
        valor.strip().lower(),
    )

    return "".join(
        caractere
        for caractere in texto
        if unicodedata.category(caractere) != "Mn"
    )


def _nome_loja_por_tipo(tipo: str) -> str:
    tipo_normalizado = (
        _normalizar_texto(tipo)
        .replace("-", " ")
        .replace("_", " ")
    )

    if tipo_normalizado == "bar":
        return "Meu Bar"

    if tipo_normalizado in {
        "casa noturna",
        "casanoturna",
        "boate",
    }:
        return "Minha Casa Noturna"

    if tipo_normalizado in {
        "eventos",
        "evento",
        "produtor de eventos",
    }:
        return "Minha Empresa de Eventos"

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=(
            f'Tipo de estabelecimento não reconhecido: "{tipo}".'
        ),
    )


def _senha_inicial_superadmin(documento: str, nome_responsavel: str) -> str:
    numeros = _somente_numeros(documento)
    nome = "".join(
        caractere for caractere in nome_responsavel.strip() if caractere.isalnum()
    )
    if len(numeros) < 6 or len(nome) < 6:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Documento e nome do responsavel devem possuir ao menos 6 caracteres.",
        )

    return f"{numeros[:6]}{nome[:6]}"
    
@router.post(
    "/{leadparceiro_id}/converter-em-parceiro",
    status_code=status.HTTP_201_CREATED,
)
def converter_lead_em_parceiro(
    leadparceiro_id: int,
    dados: ConverterLeadParceiroIn,
    _: dict = Depends(get_operador_logado),
    db: Session = Depends(get_db),
):
    lead = (
        db.query(LeadParceiro)
        .filter(
            LeadParceiro.leadparceiro_id
            == leadparceiro_id,
        )
        .first()
    )

    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead parceiro não encontrado.",
        )

    consulta_estabelecimento = db.query(LeadEstabelecimento).filter(
        LeadEstabelecimento.leadparceiro_id == leadparceiro_id
    )
    if dados.leadestabelecimento_id is not None:
        consulta_estabelecimento = consulta_estabelecimento.filter(
            LeadEstabelecimento.leadestabelecimento_id
            == dados.leadestabelecimento_id
        )
    estabelecimento = consulta_estabelecimento.order_by(
        LeadEstabelecimento.leadestabelecimento_id.asc()
    ).first()
    if not estabelecimento:
        raise HTTPException(status_code=404, detail="Estabelecimento não encontrado.")

    status_estabelecimento = (
        estabelecimento.status.value
        if hasattr(estabelecimento.status, "value")
        else estabelecimento.status
    )
    if status_estabelecimento == "CONVERTIDO":
        raise HTTPException(status_code=409, detail="Este estabelecimento já foi convertido.")
    if status_estabelecimento == "RECUSOU_PARCERIA":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Um estabelecimento que recusou a parceria não pode ser convertido.",
        )

    email_responsavel = str(dados.email_responsavel).strip().lower()
    organizacao_existente = (
        db.query(Organizacao)
        .filter(Organizacao.leadparceiro_id == leadparceiro_id)
        .first()
    )
    usuario_existente = (
        db.query(Usuario).filter(Usuario.emailuser == email_responsavel).first()
    )
    if usuario_existente and not organizacao_existente:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Já existe um usuário cadastrado com este e-mail.",
        )

    if status_estabelecimento != "ACEITOU_PARCERIA":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="O estabelecimento precisa ter aceitado a parceria antes da conversão.",
        )
    senha_inicial = secrets.token_urlsafe(9)
    primeira_conversao = organizacao_existente is None

    try:
        if primeira_conversao:
            nova_organizacao = Organizacao(
                nmorganizacao=dados.nome_organizacao.strip(),
                emailorganizacao=email_responsavel,
                telorganizacao=lead.telefone.strip(),
                sitorganizacao="ATIVA",
                leadparceiro_id=lead.leadparceiro_id,
                nmresponsavelprincipal=lead.nmresponsavel.strip(),
                tipooperacao=dados.tipo_loja,
            )
            db.add(nova_organizacao)
            db.flush()
        else:
            nova_organizacao = organizacao_existente

        nova_loja = Loja(
            organizacao_id=nova_organizacao.organizacao_id,
            leadestabelecimento_id=estabelecimento.leadestabelecimento_id,
            nmloja=dados.nome_loja.strip(),
            endloja=None,
            nrceploja=None,
            nrendeloja=None,
            dsbairroloja=None,
            dsrefeloja=None,
            sitloja="ATIVA",
            aberto24x7="N",
            nrtelloja=lead.telefone.strip(),
            nrdiavalidade=90,
            idvalidadeprod="S",
            estado_id=estabelecimento.estado_id,
            cidade_id=estabelecimento.cidade_id,
            vrtaxaprod=dados.taxa_produtos,
            vrtaxaing=dados.taxa_ingressos,
            tipoloja=dados.tipo_loja,
            atendimentofisico="N" if dados.tipo_loja == "PRODUTOR_EVENTOS" else "S",
            vendaprodutos="S" if estabelecimento.tipovenda in {"PRODUTOS", "AMBOS"} else "N",
            vendaingressos="S" if estabelecimento.tipovenda in {"INGRESSOS", "AMBOS"} else "N",
        )

        db.add(nova_loja)

        # Obtém o loja_id antes do commit.
        db.flush()

        categorias = [
            Categoria(
                organizacao_id=nova_organizacao.organizacao_id,
                loja_id=nova_loja.loja_id,
                nmcategoria=nome_categoria,
                sitcategoria="ATIVA",
                idordcategoria=ordem,
            )
            for ordem, nome_categoria in enumerate(CATEGORIAS_PADRAO, start=1)
        ]
        db.add_all(categorias)

        if primeira_conversao:
            superadmin = Usuario(
                organizacao_id=nova_organizacao.organizacao_id,
                loja_id=None,
                nmusuario=f"SUPERADMIN {nova_organizacao.nmorganizacao}",
                emailuser=email_responsavel,
                senhahashuser=hash_senha(senha_inicial),
                dscargo="SUPERADMIN",
                situsuario="ATIVO",
            )
            db.add(superadmin)
            db.flush()
        else:
            superadmin = (
                db.query(Usuario)
                .filter(
                    Usuario.organizacao_id == nova_organizacao.organizacao_id,
                    Usuario.dscargo == "SUPERADMIN",
                )
                .first()
            )
            if not superadmin:
                raise HTTPException(status_code=409, detail="SUPERADMIN da organização não encontrado.")

        estabelecimento.status = "CONVERTIDO"
        estabelecimento.dtconversao = datetime.now()
        restantes = (
            db.query(LeadEstabelecimento)
            .filter(
                LeadEstabelecimento.leadparceiro_id == leadparceiro_id,
                LeadEstabelecimento.leadestabelecimento_id
                != estabelecimento.leadestabelecimento_id,
                LeadEstabelecimento.status != "CONVERTIDO",
            )
            .count()
        )
        lead.status = "CONVERTIDO" if restantes == 0 else "NEGOCIANDO"

        resultado = {
            "ok": True,
            "mensagem": "Lead convertido em parceiro com sucesso.",
            "leadparceiro_id": lead.leadparceiro_id,
            "leadestabelecimento_id": estabelecimento.leadestabelecimento_id,
            "status_lead": lead.status,
            "status_estabelecimento": "CONVERTIDO",
            "tipo": estabelecimento.tipo,
            "tipovenda": estabelecimento.tipovenda,
            "organizacao": {
                "organizacao_id": nova_organizacao.organizacao_id,
                "nome": nova_organizacao.nmorganizacao,
            },
            "loja": {
                "loja_id": nova_loja.loja_id,
                "nome": nova_loja.nmloja,
            },
            "superadmin": {
                "usuario_id": superadmin.usuario_id,
                "nome": superadmin.nmusuario,
                "email": superadmin.emailuser,
                "senha_inicial": senha_inicial if primeira_conversao else None,
                "convite_enviado": False,
            },
            "categorias": [categoria.nmcategoria for categoria in categorias],
        }

        db.commit()

    except HTTPException:
        db.rollback()
        raise

    except IntegrityError as erro:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Não foi possível converter o lead. "
                "Verifique se o CNPJ ou outro dado "
                "já está cadastrado."
            ),
        ) from erro

    except Exception as erro:
        db.rollback()

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=f"Erro ao converter lead: {str(erro)}",
        ) from erro

    # O convite é uma operação externa e só é enviado depois que toda a
    # conversão foi confirmada no banco. Uma indisponibilidade do provedor de
    # e-mail não transforma uma conversão concluída em erro HTTP 500.
    if primeira_conversao:
        try:
            enviar_convite_parceiro(
                destinatario=email_responsavel,
                nome_responsavel=lead.nmresponsavel,
                nome_organizacao=resultado["organizacao"]["nome"],
                senha_inicial=senha_inicial,
            )
            resultado["superadmin"]["convite_enviado"] = True
        except Exception:
            traceback.print_exc()

    return resultado


@router.post("/{leadparceiro_id}/reenviar-convite-parceiro")
def reenviar_convite_parceiro_convertido(
    leadparceiro_id: int,
    _: dict = Depends(get_operador_logado),
    db: Session = Depends(get_db),
):
    lead = (
        db.query(LeadParceiro)
        .filter(LeadParceiro.leadparceiro_id == leadparceiro_id)
        .first()
    )
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado.")
    if lead.status != "CONVERTIDO":
        raise HTTPException(
            status_code=409,
            detail="Somente um lead convertido pode receber um novo convite.",
        )

    organizacao = (
        db.query(Organizacao)
        .filter(Organizacao.leadparceiro_id == leadparceiro_id)
        .first()
    )
    if not organizacao:
        raise HTTPException(
            status_code=409,
            detail="A organização criada para este lead não foi encontrada.",
        )

    superadmin = (
        db.query(Usuario)
        .filter(
            Usuario.organizacao_id == organizacao.organizacao_id,
            Usuario.dscargo == "SUPERADMIN",
        )
        .first()
    )
    if not superadmin:
        raise HTTPException(
            status_code=409,
            detail="O usuário administrador do parceiro não foi encontrado.",
        )

    senha_inicial = secrets.token_urlsafe(9)
    try:
        superadmin.senhahashuser = hash_senha(senha_inicial)
        db.commit()
    except Exception as erro:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Não foi possível gerar uma nova senha para o parceiro.",
        ) from erro

    convite_enviado = True
    try:
        enviar_convite_parceiro(
            destinatario=superadmin.emailuser,
            nome_responsavel=lead.nmresponsavel,
            nome_organizacao=organizacao.nmorganizacao,
            senha_inicial=senha_inicial,
        )
    except Exception:
        convite_enviado = False
        traceback.print_exc()

    return {
        "ok": True,
        "convite_enviado": convite_enviado,
        "email": superadmin.emailuser,
        "senha_inicial": senha_inicial,
    }
