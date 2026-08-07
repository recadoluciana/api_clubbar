import os, shutil, uuid
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session
from app.core.security import get_usuario_logado
from app.database import get_db
from app.models.loja import Loja
from app.models.lojaconteudo import LojaConteudo
from app.models.lojapoliticaingresso import LojaPoliticaIngresso
from app.schemas.lojaperfil import LojaConteudoIn, LojaPoliticaIngressoIn
from app.core.config import UPLOAD_LOJAS
router=APIRouter(prefix="/lojas",tags=["Perfil completo da loja"])
def _loja(db,loja_id,payload):
    try: org=int(payload["organizacao_id"])
    except (KeyError,TypeError,ValueError): raise HTTPException(403,"Organização não identificada no login.")
    item=db.query(Loja).filter(Loja.loja_id==loja_id,Loja.organizacao_id==org).first()
    if not item: raise HTTPException(404,"Loja não encontrada.")
def _conteudo(x): return {"loja_id":x.loja_id,"dsdetalhadaloja":x.dsdetalhadaloja,"fotos":x.fotos or [],"publicacoes":x.publicacoes or [],"videos":x.videos or [],"configuracoes":x.configuracoes or {}}
def _politica(x): return {"loja_id":x.loja_id,"dspoliticaingresso":x.dspoliticaingresso,"urlmapaingressos":x.urlmapaingressos,"dsmapaingressos":x.dsmapaingressos,"dsorientacoesacesso":x.dsorientacoesacesso,"configuracoes":x.configuracoes or {}}
@router.get("/{loja_id}/conteudo")
def obter_conteudo(loja_id:int,payload=Depends(get_usuario_logado),db:Session=Depends(get_db)):
    _loja(db,loja_id,payload);x=db.query(LojaConteudo).filter(LojaConteudo.loja_id==loja_id).first();return _conteudo(x) if x else {"loja_id":loja_id,"dsdetalhadaloja":None,"fotos":[],"publicacoes":[],"videos":[],"configuracoes":{}}
@router.put("/{loja_id}/conteudo")
def salvar_conteudo(loja_id:int,dados:LojaConteudoIn,payload=Depends(get_usuario_logado),db:Session=Depends(get_db)):
    _loja(db,loja_id,payload);x=db.query(LojaConteudo).filter(LojaConteudo.loja_id==loja_id).first() or LojaConteudo(loja_id=loja_id)
    for k,v in dados.model_dump().items():setattr(x,k,v)
    db.add(x);db.commit();db.refresh(x);return _conteudo(x)
@router.post("/{loja_id}/conteudo/upload", status_code=201)
def upload_conteudo(loja_id:int,arquivo:UploadFile=File(...),payload=Depends(get_usuario_logado),db:Session=Depends(get_db)):
    _loja(db,loja_id,payload);ext=os.path.splitext(arquivo.filename or "")[1].lower()
    if ext not in {".jpg",".jpeg",".png",".webp"}:raise HTTPException(422,"Use uma imagem JPG, PNG ou WebP.")
    nome=f"conteudo_{loja_id}_{uuid.uuid4().hex}{ext}"
    with open(UPLOAD_LOJAS/nome,"wb") as destino:shutil.copyfileobj(arquivo.file,destino)
    return {"url":f"/uploads/lojas/{nome}"}
@router.delete("/{loja_id}/conteudo", status_code=204)
def excluir_conteudo(loja_id:int,payload=Depends(get_usuario_logado),db:Session=Depends(get_db)):
    _loja(db,loja_id,payload);x=db.query(LojaConteudo).filter(LojaConteudo.loja_id==loja_id).first()
    if x:db.delete(x);db.commit()
@router.get("/{loja_id}/politica-ingressos")
def obter_politica(loja_id:int,payload=Depends(get_usuario_logado),db:Session=Depends(get_db)):
    _loja(db,loja_id,payload);x=db.query(LojaPoliticaIngresso).filter(LojaPoliticaIngresso.loja_id==loja_id).first();return _politica(x) if x else {"loja_id":loja_id,"dspoliticaingresso":None,"urlmapaingressos":None,"dsmapaingressos":None,"dsorientacoesacesso":None,"configuracoes":{}}
@router.put("/{loja_id}/politica-ingressos")
def salvar_politica(loja_id:int,dados:LojaPoliticaIngressoIn,payload=Depends(get_usuario_logado),db:Session=Depends(get_db)):
    _loja(db,loja_id,payload);x=db.query(LojaPoliticaIngresso).filter(LojaPoliticaIngresso.loja_id==loja_id).first() or LojaPoliticaIngresso(loja_id=loja_id)
    for k,v in dados.model_dump().items():setattr(x,k,v)
    db.add(x);db.commit();db.refresh(x);return _politica(x)
@router.delete("/{loja_id}/politica-ingressos", status_code=204)
def excluir_politica(loja_id:int,payload=Depends(get_usuario_logado),db:Session=Depends(get_db)):
    _loja(db,loja_id,payload);x=db.query(LojaPoliticaIngresso).filter(LojaPoliticaIngresso.loja_id==loja_id).first()
    if x:db.delete(x);db.commit()
