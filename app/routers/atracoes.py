import json, os, shutil, uuid
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload
from app.core.config import UPLOAD_ATRACOES
from app.core.security import get_operador_logado, get_usuario_logado
from app.core.permissoes_loja import validar_gerenciamento_organizacao, validar_mutacao_loja
from app.database import get_db
from app.models.atracao import Atracao
from app.models.estilomusical import EstiloMusical
from app.models.organizacaoestilomusical import OrganizacaoEstiloMusical
from app.models.evento import Evento
from app.models.eventoatracao import EventoAtracao
from app.models.eventomodeloatracao import EventoModeloAtracao
from app.models.eventolote import EventoLote
from app.schemas.atracao import EventoAtracaoIn, EventoAtracaoUpdate
from app.schemas.estilomusical import EstiloMusicalIn, EstilosMusicaisImportacaoIn

router = APIRouter(tags=["Atrações"])

def _org(payload):
    try: return int(payload["organizacao_id"])
    except (KeyError, TypeError, ValueError): raise HTTPException(403, "Organização não identificada no login.")

def _validar_gestao_estilos(payload):
    cargo = str(payload.get("dscargo") or "").strip().upper()
    if payload.get("role") != "usuario" or cargo not in {"SUPERADMIN", "ADMIN", "GERENTE"}:
        raise HTTPException(403, "Somente administradores e gerentes podem gerenciar estilos musicais.")

def _estilo_item(e):
    return {
        "estilomusical_id": e.organizacaoestilomusical_id,
        "organizacaoestilomusical_id": e.organizacaoestilomusical_id,
        "estilomusical_padrao_id": e.estilomusical_id,
        "nmestilomusical": e.nmestilomusical,
        "sitestilomusical": e.sitestilomusical,
        "origem": "CATALOGO" if e.estilomusical_id else "PERSONALIZADO",
    }

def _banner(arquivo):
    if not arquivo or not arquivo.filename: return None
    ext = os.path.splitext(arquivo.filename)[1].lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}: raise HTTPException(422, "Use uma imagem JPG, PNG ou WebP.")
    nome = f"{uuid.uuid4().hex}{ext}"
    with open(UPLOAD_ATRACOES / nome, "wb") as destino: shutil.copyfileobj(arquivo.file, destino)
    return f"/uploads/atracoes/{nome}"

def _item(a):
    estilos = [
        {
            "estilomusical_id": estilo.organizacaoestilomusical_id,
            "nmestilomusical": estilo.nmestilomusical,
        }
        for estilo in a.estilos
    ]
    return {"atracao_id":a.atracao_id,"organizacao_id":a.organizacao_id,"nmatracao":a.nmatracao,"dsestilomusical":", ".join(e["nmestilomusical"] for e in estilos) or a.dsestilomusical,"estilos":estilos,"urlbanneratracao":a.urlbanneratracao,"dsatracao":a.dsatracao}

def _ids_estilos(valor):
    if not valor:return []
    try: dados=json.loads(valor)
    except json.JSONDecodeError: dados=valor.split(",")
    if not isinstance(dados,list):raise HTTPException(422,"Formato dos estilos musicais inválido.")
    try:return list(dict.fromkeys(int(item) for item in dados))
    except (TypeError,ValueError):raise HTTPException(422,"Selecione estilos musicais válidos.")

def _aplicar_estilos(db,a,valor):
    ids=_ids_estilos(valor)
    estilos=db.query(OrganizacaoEstiloMusical).filter(OrganizacaoEstiloMusical.organizacaoestilomusical_id.in_(ids),OrganizacaoEstiloMusical.organizacao_id==a.organizacao_id,OrganizacaoEstiloMusical.sitestilomusical=="ATIVO").all() if ids else []
    if len(estilos)!=len(ids):raise HTTPException(422,"Um ou mais estilos musicais não foram encontrados.")
    a.estilos=estilos
    a.dsestilomusical=", ".join(sorted(e.nmestilomusical for e in estilos)) or None

def _prog(p):
    return {"eventoatracao_id":p.eventoatracao_id,"evento_id":p.evento_id,"atracao_id":p.atracao_id,"dtinicioatracao":p.dtinicioatracao,"dtfimatracao":p.dtfimatracao,"atracao":_item(p.atracao)}

@router.get("/atracoes")
def listar(payload=Depends(get_usuario_logado), db:Session=Depends(get_db)):
    return [_item(a) for a in db.query(Atracao).filter(Atracao.organizacao_id==_org(payload)).order_by(Atracao.nmatracao).all()]

@router.get("/estilos-musicais")
def listar_estilos_musicais(payload=Depends(get_usuario_logado),db:Session=Depends(get_db)):
    itens=db.query(OrganizacaoEstiloMusical).filter(OrganizacaoEstiloMusical.organizacao_id==_org(payload),OrganizacaoEstiloMusical.sitestilomusical=="ATIVO").order_by(OrganizacaoEstiloMusical.nmestilomusical).all()
    return [_estilo_item(e) for e in itens]

@router.get("/estilos-musicais/catalogo")
def listar_catalogo_estilos(payload=Depends(get_usuario_logado),db:Session=Depends(get_db)):
    _validar_gestao_estilos(payload)
    itens=db.query(EstiloMusical).filter(EstiloMusical.sitestilomusical=="ATIVO").order_by(EstiloMusical.nmestilomusical).all()
    return [{"estilomusical_id":e.estilomusical_id,"nmestilomusical":e.nmestilomusical,"sitestilomusical":e.sitestilomusical} for e in itens]

@router.get("/estilos-musicais/gerenciar")
def gerenciar_estilos_musicais(payload=Depends(get_usuario_logado),db:Session=Depends(get_db)):
    _validar_gestao_estilos(payload)
    itens=db.query(OrganizacaoEstiloMusical).filter(OrganizacaoEstiloMusical.organizacao_id==_org(payload)).order_by(OrganizacaoEstiloMusical.nmestilomusical).all()
    return [_estilo_item(e) for e in itens]

@router.post("/estilos-musicais", status_code=201)
def criar_estilo_musical(dados:EstiloMusicalIn,payload=Depends(get_usuario_logado),db:Session=Depends(get_db)):
    _validar_gestao_estilos(payload)
    org=_org(payload)
    existente=db.query(OrganizacaoEstiloMusical).filter(OrganizacaoEstiloMusical.organizacao_id==org,OrganizacaoEstiloMusical.nmestilomusical==dados.nmestilomusical).first()
    if existente: raise HTTPException(409,"Já existe um estilo musical com esse nome.")
    estilo=OrganizacaoEstiloMusical(organizacao_id=org,nmestilomusical=dados.nmestilomusical,sitestilomusical=dados.sitestilomusical)
    db.add(estilo)
    try: db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(409,"Já existe um estilo musical com esse nome.")
    db.refresh(estilo); return _estilo_item(estilo)

@router.put("/estilos-musicais/{estilo_id}")
def atualizar_estilo_musical(estilo_id:int,dados:EstiloMusicalIn,payload=Depends(get_usuario_logado),db:Session=Depends(get_db)):
    _validar_gestao_estilos(payload)
    org=_org(payload)
    estilo=db.query(OrganizacaoEstiloMusical).filter(OrganizacaoEstiloMusical.organizacaoestilomusical_id==estilo_id,OrganizacaoEstiloMusical.organizacao_id==org).first()
    if not estilo: raise HTTPException(404,"Estilo musical não encontrado.")
    duplicado=db.query(OrganizacaoEstiloMusical).filter(OrganizacaoEstiloMusical.organizacao_id==org,OrganizacaoEstiloMusical.nmestilomusical==dados.nmestilomusical,OrganizacaoEstiloMusical.organizacaoestilomusical_id!=estilo_id).first()
    if duplicado: raise HTTPException(409,"Já existe um estilo musical com esse nome.")
    estilo.nmestilomusical=dados.nmestilomusical; estilo.sitestilomusical=dados.sitestilomusical
    try: db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(409,"Já existe um estilo musical com esse nome.")
    db.refresh(estilo); return _estilo_item(estilo)

@router.delete("/estilos-musicais/{estilo_id}", status_code=204)
def excluir_estilo_musical(estilo_id:int,payload=Depends(get_usuario_logado),db:Session=Depends(get_db)):
    _validar_gestao_estilos(payload)
    estilo=db.query(OrganizacaoEstiloMusical).filter(OrganizacaoEstiloMusical.organizacaoestilomusical_id==estilo_id,OrganizacaoEstiloMusical.organizacao_id==_org(payload)).first()
    if not estilo: raise HTTPException(404,"Estilo musical não encontrado.")
    if estilo.atracoes: raise HTTPException(409,"O estilo está vinculado a atrações. Inative-o em vez de excluir.")
    db.delete(estilo); db.commit()

@router.post("/estilos-musicais/importar")
def importar_estilos_musicais(dados:EstilosMusicaisImportacaoIn,payload=Depends(get_usuario_logado),db:Session=Depends(get_db)):
    _validar_gestao_estilos(payload); org=_org(payload)
    ids=list(dict.fromkeys(dados.estilos_ids))
    catalogo=db.query(EstiloMusical).filter(EstiloMusical.estilomusical_id.in_(ids),EstiloMusical.sitestilomusical=="ATIVO").all()
    if len(catalogo)!=len(ids): raise HTTPException(422,"Um ou mais estilos do catálogo não foram encontrados.")
    existentes={e.estilomusical_id for e in db.query(OrganizacaoEstiloMusical).filter(OrganizacaoEstiloMusical.organizacao_id==org,OrganizacaoEstiloMusical.estilomusical_id.in_(ids)).all()}
    for estilo in catalogo:
        if estilo.estilomusical_id not in existentes:
            db.add(OrganizacaoEstiloMusical(organizacao_id=org,estilomusical_id=estilo.estilomusical_id,nmestilomusical=estilo.nmestilomusical,sitestilomusical="ATIVO"))
    try: db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(409,"Um dos estilos já existe na organização.")
    return {"importados":len(ids)-len(existentes)}

# Catálogo mestre: administrado exclusivamente pelo Clubbar Admin.
@router.get("/admin/estilos-musicais")
def admin_listar_estilos(_=Depends(get_operador_logado),db:Session=Depends(get_db)):
    return [{"estilomusical_id":e.estilomusical_id,"nmestilomusical":e.nmestilomusical,"sitestilomusical":e.sitestilomusical} for e in db.query(EstiloMusical).order_by(EstiloMusical.nmestilomusical).all()]

@router.post("/admin/estilos-musicais",status_code=201)
def admin_criar_estilo(dados:EstiloMusicalIn,_=Depends(get_operador_logado),db:Session=Depends(get_db)):
    estilo=EstiloMusical(nmestilomusical=dados.nmestilomusical,sitestilomusical=dados.sitestilomusical); db.add(estilo)
    try: db.commit()
    except IntegrityError: db.rollback(); raise HTTPException(409,"Já existe um estilo musical com esse nome.")
    db.refresh(estilo); return {"estilomusical_id":estilo.estilomusical_id,"nmestilomusical":estilo.nmestilomusical,"sitestilomusical":estilo.sitestilomusical}

@router.put("/admin/estilos-musicais/{estilo_id}")
def admin_atualizar_estilo(estilo_id:int,dados:EstiloMusicalIn,_=Depends(get_operador_logado),db:Session=Depends(get_db)):
    estilo=db.get(EstiloMusical,estilo_id)
    if not estilo: raise HTTPException(404,"Estilo musical não encontrado.")
    estilo.nmestilomusical=dados.nmestilomusical; estilo.sitestilomusical=dados.sitestilomusical
    try: db.commit()
    except IntegrityError: db.rollback(); raise HTTPException(409,"Já existe um estilo musical com esse nome.")
    return {"estilomusical_id":estilo.estilomusical_id,"nmestilomusical":estilo.nmestilomusical,"sitestilomusical":estilo.sitestilomusical}

@router.delete("/admin/estilos-musicais/{estilo_id}",status_code=204)
def admin_excluir_estilo(estilo_id:int,_=Depends(get_operador_logado),db:Session=Depends(get_db)):
    estilo=db.get(EstiloMusical,estilo_id)
    if not estilo: raise HTTPException(404,"Estilo musical não encontrado.")
    if estilo.estilos_organizacoes: raise HTTPException(409,"O estilo já foi adotado por organizações. Inative-o em vez de excluir.")
    db.delete(estilo); db.commit()

@router.post("/atracoes", status_code=201)
def criar(nmatracao:str=Form(...),dsestilomusical:str|None=Form(None),estilos_ids:str|None=Form(None),dsatracao:str|None=Form(None),urlbanneratracao:UploadFile|None=File(None),payload=Depends(get_usuario_logado),db:Session=Depends(get_db)):
    validar_gerenciamento_organizacao(payload,_org(payload))
    nome=nmatracao.strip()
    if not nome: raise HTTPException(422,"Informe o nome da atração.")
    a=Atracao(organizacao_id=_org(payload),nmatracao=nome,dsestilomusical=(dsestilomusical or "").strip() or None,dsatracao=(dsatracao or "").strip() or None,urlbanneratracao=_banner(urlbanneratracao))
    db.add(a);db.flush();_aplicar_estilos(db,a,estilos_ids);db.commit();db.refresh(a);return _item(a)

@router.put("/atracoes/{atracao_id}")
def atualizar(atracao_id:int,nmatracao:str=Form(...),dsestilomusical:str|None=Form(None),estilos_ids:str|None=Form(None),dsatracao:str|None=Form(None),urlbanneratracao:UploadFile|None=File(None),payload=Depends(get_usuario_logado),db:Session=Depends(get_db)):
    validar_gerenciamento_organizacao(payload,_org(payload))
    a=db.query(Atracao).filter(Atracao.atracao_id==atracao_id,Atracao.organizacao_id==_org(payload)).first()
    if not a: raise HTTPException(404,"Atração não encontrada.")
    if not nmatracao.strip(): raise HTTPException(422,"Informe o nome da atração.")
    a.nmatracao=nmatracao.strip();a.dsestilomusical=(dsestilomusical or "").strip() or None;a.dsatracao=(dsatracao or "").strip() or None
    _aplicar_estilos(db,a,estilos_ids)
    if urlbanneratracao and urlbanneratracao.filename: a.urlbanneratracao=_banner(urlbanneratracao)
    db.commit(); db.refresh(a); return _item(a)

@router.delete("/atracoes/{atracao_id}", status_code=204)
def excluir(atracao_id:int,payload=Depends(get_usuario_logado),db:Session=Depends(get_db)):
    validar_gerenciamento_organizacao(payload,_org(payload))
    a=db.query(Atracao).filter(Atracao.atracao_id==atracao_id,Atracao.organizacao_id==_org(payload)).first()
    if not a: raise HTTPException(404,"Atração não encontrada.")
    if db.query(EventoAtracao).filter(EventoAtracao.atracao_id==atracao_id).first(): raise HTTPException(409,"A atração está vinculada a uma agenda e não pode ser excluída.")
    if db.query(EventoModeloAtracao).filter(EventoModeloAtracao.atracao_id==atracao_id).first(): raise HTTPException(409,"A atração está vinculada a um evento padrão e não pode ser excluída.")
    db.delete(a); db.commit()

def _evento(db,evento_id,org):
    e=db.query(Evento).filter(Evento.evento_id==evento_id,Evento.organizacao_id==org).first()
    if not e: raise HTTPException(404,"Evento não encontrado.")
    return e

def _validar_horario_programacao(db, evento_id, inicio, fim, ignorar_id=None):
    conflito = db.query(EventoAtracao).filter(
        EventoAtracao.evento_id == evento_id,
        EventoAtracao.dtinicioatracao < fim,
        EventoAtracao.dtfimatracao > inicio,
    )
    if ignorar_id is not None:
        conflito = conflito.filter(EventoAtracao.eventoatracao_id != ignorar_id)
    if conflito.first():
        raise HTTPException(
            409,
            "Já existe uma atração programada nesse horário. Escolha outro período.",
        )

@router.get("/eventos/{evento_id}/atracoes")
def listar_programacao(evento_id:int,payload=Depends(get_usuario_logado),db:Session=Depends(get_db)):
    _evento(db,evento_id,_org(payload))
    q=db.query(EventoAtracao).options(joinedload(EventoAtracao.atracao)).filter(EventoAtracao.evento_id==evento_id).order_by(EventoAtracao.dtinicioatracao)
    return [_prog(p) for p in q.all()]

@router.post("/eventos/{evento_id}/atracoes", status_code=201)
def adicionar(evento_id:int,dados:EventoAtracaoIn,payload=Depends(get_usuario_logado),db:Session=Depends(get_db)):
    org=_org(payload); evento=_evento(db,evento_id,org); validar_mutacao_loja(payload,org,evento.loja_id)
    if not db.query(Atracao).filter(Atracao.atracao_id==dados.atracao_id,Atracao.organizacao_id==org).first(): raise HTTPException(404,"Atração não encontrada.")
    _validar_horario_programacao(db,evento_id,dados.dtinicioatracao,dados.dtfimatracao)
    p=EventoAtracao(evento_id=evento_id,**dados.model_dump()); db.add(p); db.commit()
    p=db.query(EventoAtracao).options(joinedload(EventoAtracao.atracao)).filter(EventoAtracao.eventoatracao_id==p.eventoatracao_id).first(); return _prog(p)

@router.put("/eventos/atracoes/{programacao_id}")
def editar_programacao(programacao_id:int,dados:EventoAtracaoUpdate,payload=Depends(get_usuario_logado),db:Session=Depends(get_db)):
    org=_org(payload); p=db.query(EventoAtracao).options(joinedload(EventoAtracao.atracao)).join(Evento).filter(EventoAtracao.eventoatracao_id==programacao_id,Evento.organizacao_id==org).first()
    if not p: raise HTTPException(404,"Programação não encontrada.")
    evento=_evento(db,p.evento_id,org); validar_mutacao_loja(payload,org,evento.loja_id)
    vals=dados.model_dump(exclude_none=True)
    if "atracao_id" in vals and not db.query(Atracao).filter(Atracao.atracao_id==vals["atracao_id"],Atracao.organizacao_id==org).first(): raise HTTPException(404,"Atração não encontrada.")
    inicio=vals.get("dtinicioatracao",p.dtinicioatracao); fim=vals.get("dtfimatracao",p.dtfimatracao)
    if fim<=inicio: raise HTTPException(422,"O fim da atração deve ser posterior ao início.")
    _validar_horario_programacao(db,p.evento_id,inicio,fim,p.eventoatracao_id)
    for k,v in vals.items(): setattr(p,k,v)
    db.commit(); db.refresh(p); return _prog(p)

@router.delete("/eventos/atracoes/{programacao_id}")
def remover(programacao_id:int,payload=Depends(get_usuario_logado),db:Session=Depends(get_db)):
    org = _org(payload)
    p=db.query(EventoAtracao).join(Evento).filter(EventoAtracao.eventoatracao_id==programacao_id,Evento.organizacao_id==org).first()
    if not p: raise HTTPException(404,"Programação não encontrada.")
    evento = db.query(Evento).filter(Evento.evento_id == p.evento_id, Evento.organizacao_id == org).first()
    validar_mutacao_loja(payload,org,evento.loja_id)
    try:
        db.delete(p)
        db.commit()
        return {"evento_excluido": False, "mensagem": "Atração removida da agenda."}
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Não foi possível excluir o evento porque existem vendas ou outros registros vinculados aos lotes.")
