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
from app.schemas.leadparceiro import (
    LeadParceiroCreate,
    LeadParceiroOut,
    LeadParceiroCadastroOut,
    LeadParceiroUpdate,
    ConverterLeadParceiroIn,
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
from app.services.email_service import enviar_acesso_portal_lead


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
    }


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

    return [
        _serializar_lead(
            lead,
            estado,
            cidade,
            origem,
        )
        for lead, estado, cidade, origem in resultados
    ]


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

    return _serializar_lead(
        lead,
        estado,
        cidade,
    )


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

        db.add(LeadMensagem(
            leadparceiro_id=lead.leadparceiro_id,
            origem='CLUBBAR',
            mensagem='Ola! Recebemos seu interesse. Use este portal para conversar com nossa equipe e acompanhar os proximos passos.',
            lida='N',
        ))
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

    if lead.status == "CONVERTIDO":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este lead já foi convertido em parceiro.",
        )

    if lead.status == "RECUSOU_PARCERIA":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Um lead que recusou a parceria não pode "
                "ser convertido."
            ),
        )

    if (
        lead.status == "CONVERTIDO"
        and dados.status is not None
        and dados.status != "CONVERTIDO"
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "O status de um lead convertido "
                "não pode ser alterado."
            ),
        )

    email_responsavel = str(dados.email_responsavel).strip().lower()
    if db.query(Usuario).filter(Usuario.emailuser == email_responsavel).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Já existe um usuário cadastrado com este e-mail.",
        )

    if lead.status != "ACEITOU_PARCERIA":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="O lead precisa ter aceitado a parceria antes da conversão.",
        )
    senha_inicial = secrets.token_urlsafe(9)

    try:
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

        # Obtém o organizacao_id sem finalizar a transação.
        db.flush()

        nova_loja = Loja(
            organizacao_id=nova_organizacao.organizacao_id,
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
            estado_id=lead.estado_id,
            cidade_id=lead.cidade_id,
            vrtaxaprod=dados.taxa_produtos,
            vrtaxaing=dados.taxa_ingressos,
            tipoloja=dados.tipo_loja,
            atendimentofisico="N" if dados.tipo_loja == "PRODUTOR_EVENTOS" else "S",
            vendaprodutos="S" if lead.tipovenda in {"PRODUTOS", "AMBOS"} else "N",
            vendaingressos="S" if lead.tipovenda in {"INGRESSOS", "AMBOS"} else "N",
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

        lead.status = "CONVERTIDO"

        db.commit()

        db.refresh(nova_organizacao)
        db.refresh(nova_loja)
        db.refresh(lead)

        try:
            enviar_acesso_portal_lead(
                lead.email,
                lead.nmresponsavel,
                acesso_portal,
            )
        except Exception:
            traceback.print_exc()

        convite_enviado = True
        try:
            enviar_convite_parceiro(
                destinatario=email_responsavel,
                nome_responsavel=lead.nmresponsavel,
                nome_organizacao=nova_organizacao.nmorganizacao,
                senha_inicial=senha_inicial,
            )
        except Exception:
            convite_enviado = False
            traceback.print_exc()

        return {
            "ok": True,
            "mensagem": (
                "Lead convertido em parceiro com sucesso."
            ),
            "leadparceiro_id": lead.leadparceiro_id,
            "status_lead": lead.status,
            "tipo": lead.tipo,
            "tipovenda": lead.tipovenda,
            "organizacao": {
                "organizacao_id": (
                    nova_organizacao.organizacao_id
                ),
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
                "senha_inicial": senha_inicial,
                "convite_enviado": convite_enviado,
            },
            "categorias": [categoria.nmcategoria for categoria in categorias],
        }

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

        import traceback
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=f"Erro ao converter lead: {str(erro)}",
        ) from erro
