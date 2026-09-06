from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload
from app.core.security import get_usuario_logado
from app.core.permissoes_loja import validar_mutacao_loja
from app.database import get_db
from app.models.evento import Evento
from app.models.eventoatracao import EventoAtracao
from app.models.atracao import Atracao
from app.models.eventolote import EventoLote
from app.models.loja import Loja
from app.schemas.atracao import EventoRapidoAgendaIn

router=APIRouter(prefix="/agenda-mensal",tags=["Agenda mensal"])

@router.post("/evento-rapido", status_code=201)
def criar_evento_rapido(dados: EventoRapidoAgendaIn, payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    if dados.dtinicioatracao.date() < datetime.now().date():
        raise HTTPException(422, "Não é permitido criar eventos em datas passadas.")
    try:
        org=int(payload["organizacao_id"])
    except (KeyError,TypeError,ValueError):
        raise HTTPException(403,"Organização não identificada no login.")
    loja=db.query(Loja).filter(Loja.loja_id==dados.loja_id,Loja.organizacao_id==org).first()
    if not loja: raise HTTPException(404,"Loja não encontrada.")
    validar_mutacao_loja(payload,loja.organizacao_id,loja.loja_id)
    if not loja.qtcpdloja or loja.qtcpdloja <= 0:
        raise HTTPException(422,"Informe a capacidade total da loja antes de criar eventos.")
    atracao=db.query(Atracao).filter(Atracao.atracao_id==dados.atracao_id,Atracao.organizacao_id==org).first()
    if not atracao: raise HTTPException(404,"Atração não encontrada.")
    evento=Evento(
        organizacao_id=org,loja_id=loja.loja_id,
        nmtituloevento=dados.nmtituloevento,
        dsdescevento=atracao.dsatracao,
        dtinicioevento=dados.dtinicioatracao,dtfimevento=None,
        nmlocalevento=None,dsendlocevento=None,
        urlbannerevento=atracao.urlbanneratracao,statusevento="ATIVO",
    )
    try:
        db.add(evento); db.flush()
        programacao=EventoAtracao(evento_id=evento.evento_id,atracao_id=atracao.atracao_id,dtinicioatracao=dados.dtinicioatracao,dtfimatracao=dados.dtfimatracao)
        lote=EventoLote(
            organizacao_id=org,loja_id=loja.loja_id,evento_id=evento.evento_id,
            nmlote="Lote único",vrprecolote=dados.preco_lote,
            qttotallote=loja.qtcpdloja,qtvendidalote=0,
            dtiniciovenda=datetime.now(),dtfimvenda=dados.dtinicioatracao,statuslote="ATIVO",
        )
        db.add_all([programacao,lote]); db.commit(); db.refresh(evento); db.refresh(lote)
        return {"evento_id":evento.evento_id,"lote_id":lote.lote_id,"mensagem":"Evento, atração e lote criados com sucesso."}
    except Exception:
        db.rollback(); raise

@router.get("")
def listar(loja_id:int,ano:int=Query(ge=2000,le=2200),mes:int=Query(ge=1,le=12),payload=Depends(get_usuario_logado),db:Session=Depends(get_db)):
    try: org=int(payload["organizacao_id"])
    except (KeyError,TypeError,ValueError): raise HTTPException(403,"Organização não identificada no login.")
    inicio=datetime(ano,mes,1); fim=datetime(ano+(mes==12),1 if mes==12 else mes+1,1)
    eventos=(db.query(Evento).outerjoin(EventoAtracao,EventoAtracao.evento_id==Evento.evento_id).filter(
        Evento.organizacao_id==org, Evento.loja_id==loja_id,
        or_(
            (Evento.dtinicioevento<fim) & or_(Evento.dtfimevento>=inicio,Evento.dtinicioevento>=inicio),
            (EventoAtracao.dtinicioatracao>=inicio) & (EventoAtracao.dtinicioatracao<fim),
        ),
    ).distinct().order_by(Evento.dtinicioevento).all())
    saida=[]
    for e in eventos:
        ps=db.query(EventoAtracao).options(joinedload(EventoAtracao.atracao)).filter(EventoAtracao.evento_id==e.evento_id).order_by(EventoAtracao.dtinicioatracao).all()
        saida.append({"evento_id":e.evento_id,"organizacao_id":e.organizacao_id,"loja_id":e.loja_id,"nmtituloevento":e.nmtituloevento,"dtinicioevento":e.dtinicioevento,"dtfimevento":e.dtfimevento,"statusevento":e.statusevento,"urlbannerevento":e.urlbannerevento,"atracoes":[{"eventoatracao_id":p.eventoatracao_id,"atracao_id":p.atracao_id,"dtinicioatracao":p.dtinicioatracao,"dtfimatracao":p.dtfimatracao,"atracao":{"atracao_id":p.atracao.atracao_id,"organizacao_id":p.atracao.organizacao_id,"nmatracao":p.atracao.nmatracao,"dsestilomusical":p.atracao.dsestilomusical,"estilos":[{"estilomusical_id":x.organizacaoestilomusical_id,"nmestilomusical":x.nmestilomusical} for x in p.atracao.estilos],"urlbanneratracao":p.atracao.urlbanneratracao,"dsatracao":p.atracao.dsatracao}} for p in ps]})
    return saida
