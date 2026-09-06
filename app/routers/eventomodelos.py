from calendar import monthrange
from datetime import datetime, timedelta
from decimal import Decimal
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.permissoes_loja import validar_mutacao_loja
from app.core.security import get_usuario_logado
from app.database import get_db
from app.models.evento import Evento
from app.models.eventolote import EventoLote
from app.models.eventomodelo import EventoModelo
from app.models.loja import Loja
from app.routers.eventos import salvar_banner_evento
from app.schemas.eventomodelo import AgendarEventoModeloIn

router = APIRouter(prefix="/eventos-modelos", tags=["Eventos padrão"])

def _org(payload):
    try: return int(payload["organizacao_id"])
    except (KeyError, TypeError, ValueError): raise HTTPException(403, "Organização não identificada.")

def _item(x):
    return {"evento_id":x.eventomodelo_id,"eventomodelo_id":x.eventomodelo_id,"organizacao_id":x.organizacao_id,"loja_id":x.loja_id,"nmtituloevento":x.nmtituloevento,"dsdescevento":x.dsdescevento,"dspoliticacancelamento":x.dspoliticacancelamento,"dspoliticareembolso":x.dspoliticareembolso,"dspoliticacashback":x.dspoliticacashback,"dtinicioevento":None,"dtfimevento":None,"nmlocalevento":x.nmlocalevento,"dsendlocevento":x.dsendlocevento,"urlbannerevento":x.urlbannerevento,"statusevento":x.statusevento,"vrprecolote":float(x.vrprecolote or 0),"qttotallote":x.qttotallote}

def _modelo(db,id,org):
    x=db.query(EventoModelo).filter(EventoModelo.eventomodelo_id==id,EventoModelo.organizacao_id==org).first()
    if not x: raise HTTPException(404,"Evento padrão não encontrado.")
    return x

@router.get("")
def listar(loja_id:int,payload=Depends(get_usuario_logado),db:Session=Depends(get_db)):
    org=_org(payload); validar_mutacao_loja(payload,org,loja_id)
    return [_item(x) for x in db.query(EventoModelo).filter(EventoModelo.organizacao_id==org,EventoModelo.loja_id==loja_id).order_by(EventoModelo.nmtituloevento).all()]

@router.post("",status_code=201)
def criar(organizacao_id:int=Form(...),loja_id:int=Form(...),nmtituloevento:str=Form(...),dsdescevento:str|None=Form(None),dspoliticacancelamento:str|None=Form(None),dspoliticareembolso:str|None=Form(None),dspoliticacashback:str|None=Form(None),nmlocalevento:str|None=Form(None),dsendlocevento:str|None=Form(None),statusevento:str=Form("ATIVO"),vrprecolote:Decimal=Form(0),qttotallote:int|None=Form(None),urlbannerevento:UploadFile|None=File(None),payload=Depends(get_usuario_logado),db:Session=Depends(get_db)):
    org=_org(payload)
    if organizacao_id!=org: raise HTTPException(403,"Organização inválida.")
    validar_mutacao_loja(payload,org,loja_id)
    x=EventoModelo(organizacao_id=org,loja_id=loja_id,nmtituloevento=nmtituloevento.strip(),dsdescevento=dsdescevento,dspoliticacancelamento=dspoliticacancelamento,dspoliticareembolso=dspoliticareembolso,dspoliticacashback=dspoliticacashback,nmlocalevento=nmlocalevento,dsendlocevento=dsendlocevento,statusevento=statusevento.upper(),vrprecolote=vrprecolote,qttotallote=qttotallote,urlbannerevento=salvar_banner_evento(urlbannerevento))
    db.add(x);db.commit();db.refresh(x);return _item(x)

@router.put("/{modelo_id}")
def atualizar(modelo_id:int,nmtituloevento:str|None=Form(None),dsdescevento:str|None=Form(None),dspoliticacancelamento:str|None=Form(None),dspoliticareembolso:str|None=Form(None),dspoliticacashback:str|None=Form(None),nmlocalevento:str|None=Form(None),dsendlocevento:str|None=Form(None),statusevento:str|None=Form(None),vrprecolote:Decimal|None=Form(None),qttotallote:int|None=Form(None),urlbannerevento:UploadFile|None=File(None),payload=Depends(get_usuario_logado),db:Session=Depends(get_db)):
    x=_modelo(db,modelo_id,_org(payload));validar_mutacao_loja(payload,x.organizacao_id,x.loja_id)
    for k,v in {"nmtituloevento":nmtituloevento,"dsdescevento":dsdescevento,"dspoliticacancelamento":dspoliticacancelamento,"dspoliticareembolso":dspoliticareembolso,"dspoliticacashback":dspoliticacashback,"nmlocalevento":nmlocalevento,"dsendlocevento":dsendlocevento,"statusevento":statusevento,"vrprecolote":vrprecolote,"qttotallote":qttotallote}.items():
        if v is not None:setattr(x,k,v.upper() if k=="statusevento" else v)
    if urlbannerevento and urlbannerevento.filename:x.urlbannerevento=salvar_banner_evento(urlbannerevento)
    db.commit();db.refresh(x);return _item(x)

@router.delete("/{modelo_id}",status_code=204)
def excluir(modelo_id:int,payload=Depends(get_usuario_logado),db:Session=Depends(get_db)):
    x=_modelo(db,modelo_id,_org(payload));validar_mutacao_loja(payload,x.organizacao_id,x.loja_id)
    if db.query(Evento).filter(Evento.eventomodelo_id==modelo_id).first():raise HTTPException(409,"O evento padrão já possui datas na agenda. Inative-o em vez de excluir.")
    db.delete(x);db.commit()

def _somar_mes(data:datetime,meses:int):
    total=data.month-1+meses; ano=data.year+total//12; mes=total%12+1
    return data.replace(year=ano,month=mes,day=min(data.day,monthrange(ano,mes)[1]))

@router.post("/{modelo_id}/agendar",status_code=201)
def agendar(modelo_id:int,dados:AgendarEventoModeloIn,payload=Depends(get_usuario_logado),db:Session=Depends(get_db)):
    x=_modelo(db,modelo_id,_org(payload));validar_mutacao_loja(payload,x.organizacao_id,x.loja_id)
    loja=db.get(Loja,x.loja_id); duracao=(dados.dtfim-dados.dtinicio) if dados.dtfim else None; ids=[]
    for i in range(dados.repeticoes):
        inicio=_somar_mes(dados.dtinicio,i) if dados.recorrencia=="MENSAL" else dados.dtinicio+timedelta(days=i*(14 if dados.recorrencia=="QUINZENAL" else 7 if dados.recorrencia=="SEMANAL" else 0))
        evento=Evento(organizacao_id=x.organizacao_id,loja_id=x.loja_id,eventomodelo_id=x.eventomodelo_id,nmtituloevento=x.nmtituloevento,dsdescevento=x.dsdescevento,dspoliticacancelamento=x.dspoliticacancelamento,dspoliticareembolso=x.dspoliticareembolso,dspoliticacashback=x.dspoliticacashback,dtinicioevento=inicio,dtfimevento=inicio+duracao if duracao else None,nmlocalevento=x.nmlocalevento,dsendlocevento=x.dsendlocevento,urlbannerevento=x.urlbannerevento,statusevento="ATIVO")
        db.add(evento);db.flush()
        lote=EventoLote(organizacao_id=x.organizacao_id,loja_id=x.loja_id,evento_id=evento.evento_id,nmlote="Ingresso único",vrprecolote=x.vrprecolote,qttotallote=x.qttotallote or getattr(loja,"qtcpdloja",None),qtvendidalote=0,dtiniciovenda=datetime.now(),dtfimvenda=inicio,statuslote="ATIVO")
        db.add(lote);ids.append(evento.evento_id)
    db.commit();return {"sessoes_criadas":len(ids),"evento_ids":ids}
