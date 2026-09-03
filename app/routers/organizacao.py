import traceback

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.permissoes_loja import validar_edicao_organizacao
from app.core.security import get_usuario_logado
from app.database import get_db
from app.models.organizacao import Organizacao
from app.models.leadparceiro import LeadParceiro
from app.models.usuario import Usuario
from app.schemas.organizacao import OrganizacaoCreate, OrganizacaoUpdate


router = APIRouter(tags=['Organizacoes'])


def _out(organizacao: Organizacao, db: Session) -> dict:
    nome_lead_origem = None
    if organizacao.leadparceiro_id:
        nome_lead_origem = db.query(LeadParceiro.nmresponsavel).filter(
            LeadParceiro.leadparceiro_id == organizacao.leadparceiro_id
        ).scalar()
    return {
        'organizacao_id': organizacao.organizacao_id,
        'nmorganizacao': organizacao.nmorganizacao,
        'nmresponsavelprincipal': organizacao.nmresponsavelprincipal,
        'emailorganizacao': organizacao.emailorganizacao,
        'telorganizacao': organizacao.telorganizacao,
        'leadparceiro_id': organizacao.leadparceiro_id,
        'nmleadorigem': nome_lead_origem,
        'sitorganizacao': organizacao.sitorganizacao,
        'dtcriacao': organizacao.dtcriacao,
        'dtultatu': organizacao.dtultatu,
    }


@router.get('/organizacoes/usuario/{usuario_id}')
def listar_organizacao_do_usuario(usuario_id: int, db: Session = Depends(get_db)):
    organizacao = (
        db.query(Organizacao)
        .join(Usuario, Usuario.organizacao_id == Organizacao.organizacao_id)
        .filter(Usuario.usuario_id == usuario_id)
        .first()
    )
    if not organizacao:
        raise HTTPException(status_code=404, detail='Organizacao nao encontrada para este usuario')
    return _out(organizacao, db)


@router.put('/organizacoes/usuario/{usuario_id}')
def atualizar_organizacao_do_usuario(
    usuario_id: int,
    dados: OrganizacaoUpdate,
    usuario_logado: dict = Depends(get_usuario_logado),
    db: Session = Depends(get_db),
):
    usuario = db.query(Usuario).filter(Usuario.usuario_id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail='Usuario nao encontrado')
    organizacao = db.query(Organizacao).filter(
        Organizacao.organizacao_id == usuario.organizacao_id
    ).first()
    if not organizacao:
        raise HTTPException(status_code=404, detail='Organizacao nao encontrada')
    if int(usuario_logado.get('sub') or 0) != usuario_id:
        raise HTTPException(status_code=403, detail='Usuario do login nao confere')
    validar_edicao_organizacao(usuario_logado, usuario.organizacao_id)
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(organizacao, campo, valor)
    try:
        db.commit()
        db.refresh(organizacao)
        return {'mensagem': 'Organizacao atualizada com sucesso', **_out(organizacao, db)}
    except Exception as erro:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f'Erro ao atualizar organizacao: {erro}')


@router.post('/organizacoes')
def cadastrar_organizacao(dados: OrganizacaoCreate, db: Session = Depends(get_db)):
    existe = db.query(Organizacao).filter(
        Organizacao.emailorganizacao == dados.emailorganizacao
    ).first()
    if existe:
        raise HTTPException(status_code=400, detail='Ja existe uma organizacao com este e-mail')
    try:
        nova = Organizacao(**dados.model_dump(), sitorganizacao='ATIVA')
        db.add(nova)
        db.commit()
        db.refresh(nova)
        return {'mensagem': 'Organizacao cadastrada com sucesso', **_out(nova, db)}
    except Exception as erro:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(erro))
