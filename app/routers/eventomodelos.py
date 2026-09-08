from calendar import monthrange
from datetime import datetime, timedelta
from decimal import Decimal
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session, joinedload

from app.core.permissoes_loja import validar_gerenciamento_organizacao, validar_mutacao_loja
from app.core.security import get_usuario_logado
from app.database import get_db
from app.models.evento import Evento
from app.models.eventomodelo import EventoModelo
from app.models.eventomodeloatracao import EventoModeloAtracao
from app.services.agenda_service import obter_ou_criar_agenda
from app.models.eventoatracao import EventoAtracao
from app.models.atracao import Atracao
from app.models.loja import Loja
from app.routers.eventos import salvar_banner_evento
from app.schemas.eventomodelo import AgendarEventoModeloIn, EventoModeloAtracaoIn, EventoModeloAtracaoUpdate
from app.services.evento_imagem_service import imagem_evento_modelo
from app.services.ingressos_padrao_service import criar_ingressos_pista_inteira_meia

router = APIRouter(prefix="/eventos-modelos", tags=["Eventos padrão"])

def _org(payload):
    try: return int(payload["organizacao_id"])
    except (KeyError, TypeError, ValueError): raise HTTPException(403, "Organização não identificada.")

def _item(db, x):
    return {"evento_id":x.eventomodelo_id,"eventomodelo_id":x.eventomodelo_id,"organizacao_id":x.organizacao_id,"loja_id":0,"nmtituloevento":x.nmtituloevento,"dsdescevento":x.dsdescevento,"dspoliticacancelamento":x.dspoliticacancelamento,"tipolocalevento":x.tipolocalevento,"nrceplocalevento":x.nrceplocalevento,"dtinicioevento":None,"dtfimevento":None,"nmlocalevento":x.nmlocalevento,"dsendlocevento":x.dsendlocevento,"urlbannerevento":imagem_evento_modelo(db, x),"statusevento":x.statusevento,"vrprecolote":float(x.vrprecolote or 0)}

def _modelo(db,id,org):
    x=db.query(EventoModelo).filter(EventoModelo.eventomodelo_id==id,EventoModelo.organizacao_id==org).first()
    if not x: raise HTTPException(404,"Evento padrão não encontrado.")
    return x

def _atracao_item(x):
    return {
        "eventomodeloatracao_id": x.eventomodeloatracao_id,
        "eventomodelo_id": x.eventomodelo_id,
        "atracao_id": x.atracao_id,
        "ordem": x.ordem,
        "nrminutoinicio": x.nrminutoinicio,
        "nrminutoduracao": x.nrminutoduracao,
        "atracao": {"atracao_id": x.atracao.atracao_id, "nmatracao": x.atracao.nmatracao},
    }

def _validar_atracao_modelo(db, modelo, dados, ignorar_id=None):
    atracao = db.query(Atracao).filter(Atracao.atracao_id == dados["atracao_id"], Atracao.organizacao_id == modelo.organizacao_id).first()
    if not atracao:
        raise HTTPException(404, "Atração não encontrada.")
    inicio = dados["nrminutoinicio"]
    fim = inicio + dados["nrminutoduracao"]
    existentes = db.query(EventoModeloAtracao).filter(EventoModeloAtracao.eventomodelo_id == modelo.eventomodelo_id)
    if ignorar_id is not None:
        existentes = existentes.filter(EventoModeloAtracao.eventomodeloatracao_id != ignorar_id)
    for item in existentes.all():
        if inicio < item.nrminutoinicio + item.nrminutoduracao and fim > item.nrminutoinicio:
            raise HTTPException(409, "Já existe uma atração padrão nesse horário.")
    if existentes.filter(EventoModeloAtracao.ordem == dados["ordem"]).first():
        raise HTTPException(409, "Já existe uma atração com esta ordem.")

@router.get("/{modelo_id}/atracoes")
def listar_atracoes_modelo(modelo_id:int,payload=Depends(get_usuario_logado),db:Session=Depends(get_db)):
    modelo=_modelo(db,modelo_id,_org(payload));validar_gerenciamento_organizacao(payload,modelo.organizacao_id)
    itens=db.query(EventoModeloAtracao).options(joinedload(EventoModeloAtracao.atracao)).filter(EventoModeloAtracao.eventomodelo_id==modelo_id).order_by(EventoModeloAtracao.ordem,EventoModeloAtracao.nrminutoinicio).all()
    return [_atracao_item(x) for x in itens]

@router.get("/{modelo_id}/atracoes-disponiveis")
def listar_atracoes_disponiveis(modelo_id:int,payload=Depends(get_usuario_logado),db:Session=Depends(get_db)):
    modelo=_modelo(db,modelo_id,_org(payload));validar_gerenciamento_organizacao(payload,modelo.organizacao_id)
    itens=db.query(Atracao).filter(Atracao.organizacao_id==modelo.organizacao_id).order_by(Atracao.nmatracao).all()
    return [{"atracao_id":a.atracao_id,"organizacao_id":a.organizacao_id,"nmatracao":a.nmatracao,"dsestilomusical":a.dsestilomusical,"urlbanneratracao":a.urlbanneratracao,"dsatracao":a.dsatracao,"estilos":[]} for a in itens]

@router.post("/{modelo_id}/atracoes",status_code=201)
def adicionar_atracao_modelo(modelo_id:int,dados:EventoModeloAtracaoIn,payload=Depends(get_usuario_logado),db:Session=Depends(get_db)):
    modelo=_modelo(db,modelo_id,_org(payload));validar_gerenciamento_organizacao(payload,modelo.organizacao_id)
    valores=dados.model_dump();_validar_atracao_modelo(db,modelo,valores)
    item=EventoModeloAtracao(eventomodelo_id=modelo_id,**valores);db.add(item);db.commit()
    item=db.query(EventoModeloAtracao).options(joinedload(EventoModeloAtracao.atracao)).filter(EventoModeloAtracao.eventomodeloatracao_id==item.eventomodeloatracao_id).first()
    return _atracao_item(item)

@router.put("/atracoes/{item_id}")
def atualizar_atracao_modelo(item_id:int,dados:EventoModeloAtracaoUpdate,payload=Depends(get_usuario_logado),db:Session=Depends(get_db)):
    item=db.query(EventoModeloAtracao).filter(EventoModeloAtracao.eventomodeloatracao_id==item_id).first()
    if not item: raise HTTPException(404,"Atração padrão não encontrada.")
    modelo=_modelo(db,item.eventomodelo_id,_org(payload));validar_gerenciamento_organizacao(payload,modelo.organizacao_id)
    valores={"atracao_id":item.atracao_id,"ordem":item.ordem,"nrminutoinicio":item.nrminutoinicio,"nrminutoduracao":item.nrminutoduracao}
    valores.update(dados.model_dump(exclude_none=True));_validar_atracao_modelo(db,modelo,valores,item_id)
    for chave,valor in valores.items():setattr(item,chave,valor)
    db.commit();item=db.query(EventoModeloAtracao).options(joinedload(EventoModeloAtracao.atracao)).filter(EventoModeloAtracao.eventomodeloatracao_id==item_id).first();return _atracao_item(item)

@router.delete("/atracoes/{item_id}",status_code=204)
def excluir_atracao_modelo(item_id:int,payload=Depends(get_usuario_logado),db:Session=Depends(get_db)):
    item=db.query(EventoModeloAtracao).filter(EventoModeloAtracao.eventomodeloatracao_id==item_id).first()
    if not item: raise HTTPException(404,"Atração padrão não encontrada.")
    modelo=_modelo(db,item.eventomodelo_id,_org(payload));validar_gerenciamento_organizacao(payload,modelo.organizacao_id)
    db.delete(item);db.commit()

@router.get("")
def listar(payload=Depends(get_usuario_logado),db:Session=Depends(get_db)):
    org=_org(payload); validar_gerenciamento_organizacao(payload,org)
    return [_item(db, x) for x in db.query(EventoModelo).filter(EventoModelo.organizacao_id==org).order_by(EventoModelo.nmtituloevento).all()]

@router.post("",status_code=201)
def criar(organizacao_id:int=Form(...),nmtituloevento:str=Form(...),dsdescevento:str|None=Form(None),tipolocalevento:str=Form("ESTABELECIMENTO"),nrceplocalevento:str|None=Form(None),nmlocalevento:str|None=Form(None),dsendlocevento:str|None=Form(None),statusevento:str=Form("ATIVO"),vrprecolote:Decimal=Form(0),urlbannerevento:UploadFile|None=File(None),payload=Depends(get_usuario_logado),db:Session=Depends(get_db)):
    org=_org(payload)
    if organizacao_id!=org: raise HTTPException(403,"Organização inválida.")
    validar_gerenciamento_organizacao(payload,org)
    tipo=tipolocalevento.strip().upper()
    if tipo not in {"ESTABELECIMENTO","OUTRO"}: raise HTTPException(422,"Tipo de local inválido.")
    if tipo == "OUTRO" and (not nrceplocalevento or not nmlocalevento or not dsendlocevento): raise HTTPException(422,"Informe CEP, nome e endereço do outro local.")
    x=EventoModelo(organizacao_id=org,nmtituloevento=nmtituloevento.strip(),dsdescevento=dsdescevento,tipolocalevento=tipo,nrceplocalevento=nrceplocalevento if tipo=="OUTRO" else None,nmlocalevento=nmlocalevento if tipo=="OUTRO" else None,dsendlocevento=dsendlocevento if tipo=="OUTRO" else None,statusevento=statusevento.upper(),vrprecolote=vrprecolote,urlbannerevento=salvar_banner_evento(urlbannerevento))
    db.add(x);db.commit();db.refresh(x);return _item(db, x)

@router.put("/{modelo_id}")
def atualizar(modelo_id:int,nmtituloevento:str|None=Form(None),dsdescevento:str|None=Form(None),tipolocalevento:str|None=Form(None),nrceplocalevento:str|None=Form(None),nmlocalevento:str|None=Form(None),dsendlocevento:str|None=Form(None),statusevento:str|None=Form(None),vrprecolote:Decimal|None=Form(None),urlbannerevento:UploadFile|None=File(None),payload=Depends(get_usuario_logado),db:Session=Depends(get_db)):
    x=_modelo(db,modelo_id,_org(payload));validar_gerenciamento_organizacao(payload,x.organizacao_id)
    tipo=(tipolocalevento or x.tipolocalevento).strip().upper()
    if tipo not in {"ESTABELECIMENTO","OUTRO"}: raise HTTPException(422,"Tipo de local inválido.")
    for k,v in {"nmtituloevento":nmtituloevento,"dsdescevento":dsdescevento,"nmlocalevento":nmlocalevento,"dsendlocevento":dsendlocevento,"nrceplocalevento":nrceplocalevento,"statusevento":statusevento,"vrprecolote":vrprecolote}.items():
        if v is not None:setattr(x,k,v.upper() if k=="statusevento" else v)
    x.tipolocalevento=tipo
    if tipo=="ESTABELECIMENTO": x.nrceplocalevento=x.nmlocalevento=x.dsendlocevento=None
    elif not x.nrceplocalevento or not x.nmlocalevento or not x.dsendlocevento: raise HTTPException(422,"Informe CEP, nome e endereço do outro local.")
    if urlbannerevento and urlbannerevento.filename:x.urlbannerevento=salvar_banner_evento(urlbannerevento)
    db.commit();db.refresh(x);return _item(db, x)

@router.delete("/{modelo_id}",status_code=204)
def excluir(modelo_id:int,payload=Depends(get_usuario_logado),db:Session=Depends(get_db)):
    x=_modelo(db,modelo_id,_org(payload));validar_gerenciamento_organizacao(payload,x.organizacao_id)
    if db.query(Evento).filter(Evento.eventomodelo_id==modelo_id).first():raise HTTPException(409,"O evento padrão já possui datas na agenda. Inative-o em vez de excluir.")
    db.delete(x);db.commit()

def _somar_mes(data:datetime,meses:int):
    total=data.month-1+meses; ano=data.year+total//12; mes=total%12+1
    return data.replace(year=ano,month=mes,day=min(data.day,monthrange(ano,mes)[1]))

@router.post("/{modelo_id}/agendar",status_code=201)
def agendar(modelo_id:int,dados:AgendarEventoModeloIn,payload=Depends(get_usuario_logado),db:Session=Depends(get_db)):
    x=_modelo(db,modelo_id,_org(payload));validar_mutacao_loja(payload,x.organizacao_id,dados.loja_id)
    loja=db.query(Loja).filter(Loja.loja_id==dados.loja_id,Loja.organizacao_id==x.organizacao_id).first()
    if not loja: raise HTTPException(404,"Estabelecimento não encontrado.")
    duracao=(dados.dtfim-dados.dtinicio) if dados.dtfim else None; ids=[]
    atracoes_padrao=db.query(EventoModeloAtracao).filter(EventoModeloAtracao.eventomodelo_id==modelo_id).order_by(EventoModeloAtracao.ordem).all()
    for i in range(dados.repeticoes):
        inicio=_somar_mes(dados.dtinicio,i) if dados.recorrencia=="MENSAL" else dados.dtinicio+timedelta(days=i*(14 if dados.recorrencia=="QUINZENAL" else 7 if dados.recorrencia=="SEMANAL" else 0))
        agenda = obter_ou_criar_agenda(db, x.organizacao_id, loja.loja_id, inicio)
        evento=Evento(organizacao_id=x.organizacao_id,loja_id=loja.loja_id,agendamensal_id=agenda.agendamensal_id,eventomodelo_id=x.eventomodelo_id,nmtituloevento=x.nmtituloevento,dsdescevento=x.dsdescevento,dspoliticacancelamento=x.dspoliticacancelamento,dtinicioevento=inicio,dtfimevento=inicio+duracao if duracao else None,nmlocalevento=dados.local or x.nmlocalevento,dsendlocevento=dados.endereco or x.dsendlocevento,urlbannerevento=x.urlbannerevento,statusevento="ATIVO")
        db.add(evento);db.flush()
        for padrao in atracoes_padrao:
            inicio_atracao=inicio+timedelta(minutes=padrao.nrminutoinicio)
            db.add(EventoAtracao(evento_id=evento.evento_id,atracao_id=padrao.atracao_id,dtinicioatracao=inicio_atracao,dtfimatracao=inicio_atracao+timedelta(minutes=padrao.nrminutoduracao)))
        if dados.capacidade > int(getattr(loja,"qtcpdloja",0) or 0): raise HTTPException(422,"A capacidade da sessão não pode ultrapassar a capacidade do estabelecimento.")
        criar_ingressos_pista_inteira_meia(db,organizacao_id=x.organizacao_id,loja_id=loja.loja_id,evento_id=evento.evento_id,inicio_evento=inicio,preco_inteira=Decimal(str(dados.preco_inteira)) if dados.preco_inteira is not None else x.vrprecolote,capacidade=dados.capacidade)
        ids.append(evento.evento_id)
    db.commit();return {"sessoes_criadas":len(ids),"evento_ids":ids}
