import os, shutil, uuid
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session, joinedload
from app.core.config import UPLOAD_ATRACOES
from app.core.security import get_usuario_logado
from app.database import get_db
from app.models.atracao import Atracao
from app.models.evento import Evento
from app.models.eventoatracao import EventoAtracao
from app.schemas.atracao import EventoAtracaoIn, EventoAtracaoUpdate

router = APIRouter(tags=["Atrações"])

def _org(payload):
    try: return int(payload["organizacao_id"])
    except (KeyError, TypeError, ValueError): raise HTTPException(403, "Organização não identificada no login.")

def _banner(arquivo):
    if not arquivo or not arquivo.filename: return None
    ext = os.path.splitext(arquivo.filename)[1].lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}: raise HTTPException(422, "Use uma imagem JPG, PNG ou WebP.")
    nome = f"{uuid.uuid4().hex}{ext}"
    with open(UPLOAD_ATRACOES / nome, "wb") as destino: shutil.copyfileobj(arquivo.file, destino)
    return f"/uploads/atracoes/{nome}"

def _item(a):
    return {"atracao_id":a.atracao_id,"organizacao_id":a.organizacao_id,"nmatracao":a.nmatracao,"dsestilomusical":a.dsestilomusical,"urlbanneratracao":a.urlbanneratracao,"dsatracao":a.dsatracao}

def _prog(p):
    return {"eventoatracao_id":p.eventoatracao_id,"evento_id":p.evento_id,"atracao_id":p.atracao_id,"dtinicioatracao":p.dtinicioatracao,"dtfimatracao":p.dtfimatracao,"atracao":_item(p.atracao)}

@router.get("/atracoes")
def listar(payload=Depends(get_usuario_logado), db:Session=Depends(get_db)):
    return [_item(a) for a in db.query(Atracao).filter(Atracao.organizacao_id==_org(payload)).order_by(Atracao.nmatracao).all()]

@router.post("/atracoes", status_code=201)
def criar(nmatracao:str=Form(...),dsestilomusical:str|None=Form(None),dsatracao:str|None=Form(None),urlbanneratracao:UploadFile|None=File(None),payload=Depends(get_usuario_logado),db:Session=Depends(get_db)):
    nome=nmatracao.strip()
    if not nome: raise HTTPException(422,"Informe o nome da atração.")
    a=Atracao(organizacao_id=_org(payload),nmatracao=nome,dsestilomusical=(dsestilomusical or "").strip() or None,dsatracao=(dsatracao or "").strip() or None,urlbanneratracao=_banner(urlbanneratracao))
    db.add(a); db.commit(); db.refresh(a); return _item(a)

@router.put("/atracoes/{atracao_id}")
def atualizar(atracao_id:int,nmatracao:str=Form(...),dsestilomusical:str|None=Form(None),dsatracao:str|None=Form(None),urlbanneratracao:UploadFile|None=File(None),payload=Depends(get_usuario_logado),db:Session=Depends(get_db)):
    a=db.query(Atracao).filter(Atracao.atracao_id==atracao_id,Atracao.organizacao_id==_org(payload)).first()
    if not a: raise HTTPException(404,"Atração não encontrada.")
    if not nmatracao.strip(): raise HTTPException(422,"Informe o nome da atração.")
    a.nmatracao=nmatracao.strip(); a.dsestilomusical=(dsestilomusical or "").strip() or None; a.dsatracao=(dsatracao or "").strip() or None
    if urlbanneratracao and urlbanneratracao.filename: a.urlbanneratracao=_banner(urlbanneratracao)
    db.commit(); db.refresh(a); return _item(a)

@router.delete("/atracoes/{atracao_id}", status_code=204)
def excluir(atracao_id:int,payload=Depends(get_usuario_logado),db:Session=Depends(get_db)):
    a=db.query(Atracao).filter(Atracao.atracao_id==atracao_id,Atracao.organizacao_id==_org(payload)).first()
    if not a: raise HTTPException(404,"Atração não encontrada.")
    if db.query(EventoAtracao).filter(EventoAtracao.atracao_id==atracao_id).first(): raise HTTPException(409,"A atração está vinculada a uma agenda e não pode ser excluída.")
    db.delete(a); db.commit()

def _evento(db,evento_id,org):
    e=db.query(Evento).filter(Evento.evento_id==evento_id,Evento.organizacao_id==org).first()
    if not e: raise HTTPException(404,"Evento não encontrado.")
    return e

@router.get("/eventos/{evento_id}/atracoes")
def listar_programacao(evento_id:int,payload=Depends(get_usuario_logado),db:Session=Depends(get_db)):
    _evento(db,evento_id,_org(payload))
    q=db.query(EventoAtracao).options(joinedload(EventoAtracao.atracao)).filter(EventoAtracao.evento_id==evento_id).order_by(EventoAtracao.dtinicioatracao)
    return [_prog(p) for p in q.all()]

@router.post("/eventos/{evento_id}/atracoes", status_code=201)
def adicionar(evento_id:int,dados:EventoAtracaoIn,payload=Depends(get_usuario_logado),db:Session=Depends(get_db)):
    org=_org(payload); _evento(db,evento_id,org)
    if not db.query(Atracao).filter(Atracao.atracao_id==dados.atracao_id,Atracao.organizacao_id==org).first(): raise HTTPException(404,"Atração não encontrada.")
    p=EventoAtracao(evento_id=evento_id,**dados.model_dump()); db.add(p); db.commit()
    p=db.query(EventoAtracao).options(joinedload(EventoAtracao.atracao)).filter(EventoAtracao.eventoatracao_id==p.eventoatracao_id).first(); return _prog(p)

@router.put("/eventos/atracoes/{programacao_id}")
def editar_programacao(programacao_id:int,dados:EventoAtracaoUpdate,payload=Depends(get_usuario_logado),db:Session=Depends(get_db)):
    org=_org(payload); p=db.query(EventoAtracao).options(joinedload(EventoAtracao.atracao)).join(Evento).filter(EventoAtracao.eventoatracao_id==programacao_id,Evento.organizacao_id==org).first()
    if not p: raise HTTPException(404,"Programação não encontrada.")
    vals=dados.model_dump(exclude_none=True)
    if "atracao_id" in vals and not db.query(Atracao).filter(Atracao.atracao_id==vals["atracao_id"],Atracao.organizacao_id==org).first(): raise HTTPException(404,"Atração não encontrada.")
    inicio=vals.get("dtinicioatracao",p.dtinicioatracao); fim=vals.get("dtfimatracao",p.dtfimatracao)
    if fim<=inicio: raise HTTPException(422,"O fim da atração deve ser posterior ao início.")
    for k,v in vals.items(): setattr(p,k,v)
    db.commit(); db.refresh(p); return _prog(p)

@router.delete("/eventos/atracoes/{programacao_id}", status_code=204)
def remover(programacao_id:int,payload=Depends(get_usuario_logado),db:Session=Depends(get_db)):
    p=db.query(EventoAtracao).join(Evento).filter(EventoAtracao.eventoatracao_id==programacao_id,Evento.organizacao_id==_org(payload)).first()
    if not p: raise HTTPException(404,"Programação não encontrada.")
    db.delete(p); db.commit()
