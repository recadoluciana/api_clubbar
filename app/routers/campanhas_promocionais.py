from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import get_usuario_logado
from app.database import get_db
from app.models.campanha_promocional import CampanhaPromocional
from app.models.loja import Loja
from app.routers.painel_gerencial import _extrair_escopo


router = APIRouter(prefix='/campanhas-promocionais', tags=['Campanhas promocionais'])


class CampanhaIn(BaseModel):
    loja_id: int = Field(gt=0)
    titulo: str = Field(min_length=1, max_length=100)
    mensagem: str = Field(min_length=1, max_length=1024)


def _loja_permitida(loja_id: int, usuario: dict, db: Session) -> Loja:
    organizacao_id, loja_restrita = _extrair_escopo(usuario)
    if loja_restrita is not None and loja_restrita != loja_id:
        raise HTTPException(403, 'Acesso negado para este estabelecimento')
    loja = db.query(Loja).filter(Loja.loja_id == loja_id, Loja.organizacao_id == organizacao_id).first()
    if loja is None:
        raise HTTPException(404, 'Estabelecimento não encontrado')
    return loja


def _saida(c: CampanhaPromocional) -> dict:
    return {'id': c.id, 'loja_id': c.loja_id, 'titulo': c.titulo, 'mensagem': c.mensagem,
            'status': c.status, 'criado_em': c.criado_em}


@router.get('/lojas/{loja_id}')
def listar(loja_id: int, usuario=Depends(get_usuario_logado), db: Session = Depends(get_db)):
    _loja_permitida(loja_id, usuario, db)
    campanhas = db.query(CampanhaPromocional).filter_by(loja_id=loja_id).order_by(CampanhaPromocional.id.desc()).limit(100).all()
    return [_saida(c) for c in campanhas]


@router.post('', status_code=201)
def criar(dados: CampanhaIn, usuario=Depends(get_usuario_logado), db: Session = Depends(get_db)):
    _loja_permitida(dados.loja_id, usuario, db)
    titulo, mensagem = dados.titulo.strip(), dados.mensagem.strip()
    if not titulo or not mensagem:
        raise HTTPException(422, 'Informe título e mensagem.')
    try:
        usuario_id = int(usuario.get('sub'))
    except (TypeError, ValueError):
        raise HTTPException(401, 'Sessão inválida')
    campanha = CampanhaPromocional(loja_id=dados.loja_id, titulo=titulo, mensagem=mensagem, status='RASCUNHO', criado_por=usuario_id)
    db.add(campanha)
    db.commit()
    db.refresh(campanha)
    return _saida(campanha)
