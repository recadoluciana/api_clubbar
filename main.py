import os
import logging
from datetime import datetime

from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

import app.models as app_models
from app.core.config import APP_ENV, UPLOAD_DIR
from app.core.responses import ClubbarJSONResponse
from app.database import SessionLocal, engine
from app.models.contratopadrao import ContratoPadrao
from app.models.politicacompra import PoliticaCompra
from app.middleware.auditoria import AuditoriaMiddleware
from app.services.auditoria_service import registrar_eventos_auditoria

from app.routers import cidades
from app.routers import localidades
from app.routers import auth
from app.routers import organizacao
from app.routers import lojas
from app.routers import lojahorarios
from app.routers import produtos
from app.routers import categoria
from app.routers import categorias_organizacao
from app.routers import carrinho
from app.routers import compras
from app.routers import pagamentos
from app.routers import entregas
from app.routers import eventos
from app.routers import eventolotes
from app.routers import usuarios
from app.routers import clisenha
from app.routers import clientes
from app.routers import leadparceiro
from app.routers import superadmin
from app.routers import asaas_webhook
from app.routers import portalparceiro
from app.routers import painel_gerencial
from app.routers import lojaasaas
from app.routers import operadores
from app.routers import atracoes
from app.routers import agenda
from app.routers import lojaperfil
from app.routers import lojaperfil
from app.routers import financeiro
from app.routers import caixa
from app.routers import reservas_ingressos
from app.routers import cashback
from app.routers import titularfinanceiro
from app.routers import leadatendimento
from app.routers import contratolead
from app.routers import contratopadrao
from app.routers import cardapios
from app.routers import auditoria
from app.routers import eventosetores
from app.routers import eventomodelos
from app.routers import acompanhamento_vendas
from app.routers import cora
from app.routers import taxapadrao
from app.routers import manuais
from app.routers import politicas


app = FastAPI(title="clubbar API", default_response_class=ClubbarJSONResponse)

registrar_eventos_auditoria()
app.add_middleware(AuditoriaMiddleware)

logger = logging.getLogger(__name__)

origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",    
    "http://localhost:3002",
    "http://127.0.0.1:3002",    
    "http://localhost:5500",
    "http://127.0.0.1:5500",

    # Ambiente de desenvolvimento
    "https://clubbaradmin-desenvolvimento.up.railway.app",
    "https://clubbarclient-desenvolvimento.up.railway.app",

    "https://clubbar.com.br",
    "https://www.clubbar.com.br",
    "https://app.clubbar.com.br",
    "https://admin.clubbar.com.br",
    "https://api.clubbar.com.br",
    "https://parceiro.clubbar.com.br",

    # manter por enquanto durante a transição
    "https://clubbarsite-production.up.railway.app",
    "https://clubbarclient-production.up.railway.app",
    "https://clubbaradmin-production.up.railway.app",
    "https://clubbarpartner-production.up.railway.app",
    "https://bitbeer-production.up.railway.app",

    # manter por enquanto durante a transição
    "https://clubbarsite-desenvolvimento.up.railway.app",
    "https://clubbarclient-desenvolvimento.up.railway.app",
    "https://clubbaradmin-desenvolvimento.up.railway.app",
    "https://apiclubbar-desenvolvimento.up.railway.app",
    "https://clubbarpartner-desenvolvimento.up.railway.app",
]

origens_configuradas = [
    origem.strip().rstrip("/")
    for origem in os.getenv("CORS_ORIGINS", "").split(",")
    if origem.strip()
]
origins.extend(
    origem for origem in origens_configuradas if origem not in origins
)

# Aceita portas variáveis do Flutter Web, subdomínios oficiais e variações
# geradas pelo Railway somente para serviços do ecossistema Clubbar.
cors_origin_regex = (
    r"^(?:"
    r"http://(?:localhost|127\.0\.0\.1):\d+"
    r"|https://(?:[a-z0-9-]+\.)?clubbar\.com\.br"
    r"|https://(?:clubbar[a-z0-9-]*|bitbeer[a-z0-9-]*)\.up\.railway\.app"
    r")$"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info("Diretório de uploads publicado em /uploads: %s", UPLOAD_DIR)

os.makedirs("app/static", exist_ok=True)
os.makedirs("app/static/assets", exist_ok=True)

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

app.mount("/assets", StaticFiles(directory="app/static/assets"), name="assets")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(cidades.router)
app.include_router(localidades.router)
app.include_router(auth.router)
app.include_router(organizacao.router)
app.include_router(lojas.router)
app.include_router(lojahorarios.router)
app.include_router(produtos.router)
app.include_router(categoria.router)
app.include_router(categorias_organizacao.router)
app.include_router(carrinho.router)
app.include_router(compras.router)
app.include_router(pagamentos.router)
app.include_router(entregas.router)
app.include_router(eventos.router)
app.include_router(eventomodelos.router)
app.include_router(eventolotes.router)
app.include_router(usuarios.router)
app.include_router(clisenha.router)
app.include_router(clientes.router)
app.include_router(leadparceiro.router)
app.include_router(superadmin.router)
app.include_router(asaas_webhook.router)
app.include_router(portalparceiro.router)
app.include_router(painel_gerencial.router)
app.include_router(lojaasaas.router)
app.include_router(operadores.router)
app.include_router(atracoes.router)
app.include_router(agenda.router)
app.include_router(lojaperfil.router)
app.include_router(lojaperfil.router)
app.include_router(financeiro.router)
app.include_router(caixa.router)
app.include_router(reservas_ingressos.router)
app.include_router(cashback.router)
app.include_router(titularfinanceiro.router)
app.include_router(leadatendimento.router)
app.include_router(contratolead.router)
app.include_router(contratolead.portal_router)
app.include_router(contratopadrao.router)
app.include_router(cardapios.router)
app.include_router(auditoria.router)
app.include_router(eventosetores.router)
app.include_router(acompanhamento_vendas.router)
app.include_router(cora.router)
app.include_router(taxapadrao.router)
app.include_router(manuais.router)
app.include_router(politicas.router)


@app.on_event("startup")
def garantir_politica_compra_inicial() -> None:
    """Garante uma política vigente de ingresso e outra de produto."""
    PoliticaCompra.__table__.create(bind=engine, checkfirst=True)

    db = SessionLocal()
    try:
        politicas = (
            ("INGRESSO", "Política de compra de ingresso", 7, 48, 1, 24),
            ("PRODUTO", "Política de compra de produto", 7, None, None, None),
        )
        for tipo, titulo, dias, horas_cancelamento, alteracoes, horas_alteracao in politicas:
            existe_vigente = db.query(PoliticaCompra).filter(
                PoliticaCompra.sitpolitica == "VIGENTE",
                PoliticaCompra.tipopolitica == tipo,
            ).first()
            if existe_vigente:
                continue
            db.add(PoliticaCompra(
                versao="1.0",
                tipopolitica=tipo,
                titulo=titulo,
                conteudo="Texto gerado a partir dos parâmetros da política.",
                qtd_dias_cancelamento=dias,
                qtd_horas_antecedencia_cancelamento=horas_cancelamento,
                qtd_alteracoes_participante=alteracoes,
                qtd_horas_antecedencia_alteracao=horas_alteracao,
                sitpolitica="VIGENTE",
                dtiniciovigencia=datetime.now(),
            ))
        db.commit()
        logger.info("Políticas de compra iniciais verificadas.")
    except Exception:
        db.rollback()
        logger.exception("Não foi possível preparar a política de compra inicial")
        raise
    finally:
        db.close()


@app.on_event("startup")
def garantir_aviso_previo_no_contrato_padrao() -> None:
    """Inclui a redação aprovada na cláusula 11 dos modelos ainda vigentes."""
    texto_anterior = (
        "Este contrato vigora por prazo indeterminado e pode ser encerrado por "
        "qualquer parte, sem prejuízo das obrigações já constituídas."
    )
    texto_atualizado = f"{texto_anterior} Com aviso prévio de 30 dias."
    db = SessionLocal()
    try:
        contratos = db.query(ContratoPadrao).filter(
            ContratoPadrao.sitcontrato == "ATIVO",
            ContratoPadrao.conteudomodelo.contains(texto_anterior),
            ~ContratoPadrao.conteudomodelo.contains("Com aviso prévio de 30 dias."),
        ).all()
        for contrato in contratos:
            contrato.conteudomodelo = contrato.conteudomodelo.replace(
                texto_anterior, texto_atualizado
            )
        if contratos:
            db.commit()
            logger.info("Aviso prévio de 30 dias incluído no contrato padrão ativo.")
    except Exception:
        db.rollback()
        logger.exception("Não foi possível atualizar o aviso prévio do contrato padrão")
    finally:
        db.close()


@app.on_event("startup")
def remover_inicio_relativo_das_atracoes_padrao() -> None:
    """Remove a coluna obsoleta após a publicação da programação sequencial."""
    try:
        inspector = inspect(engine)
        if "eventomodeloatracao" not in inspector.get_table_names():
            return
        colunas = {
            coluna["name"]
            for coluna in inspector.get_columns("eventomodeloatracao")
        }
        if "nrminutoinicio" not in colunas:
            return

        verificacoes = inspector.get_check_constraints("eventomodeloatracao")
        with engine.begin() as conexao:
            for verificacao in verificacoes:
                expressao = (verificacao.get("sqltext") or "").lower()
                nome = verificacao.get("name")
                if nome and "nrminutoinicio" in expressao:
                    nome_seguro = nome.replace("`", "``")
                    conexao.execute(
                        text(
                            "ALTER TABLE eventomodeloatracao "
                            f"DROP CHECK `{nome_seguro}`"
                        )
                    )
            conexao.execute(
                text(
                    "ALTER TABLE eventomodeloatracao "
                    "DROP COLUMN nrminutoinicio"
                )
            )
        logger.info("Campo de início relativo removido das atrações padrão.")
    except Exception:
        logger.exception(
            "Não foi possível remover o campo de início relativo das atrações padrão"
        )


@app.on_event("startup")
def garantir_capacidade_evento_agendado() -> None:
    """Aplica a migração obrigatória antes de expor o novo controle de lotação."""
    try:
        inspector = inspect(engine)
        if "evento" not in inspector.get_table_names():
            return
        colunas = {coluna["name"] for coluna in inspector.get_columns("evento")}
        with engine.begin() as conexao:
            if "qtcapacidadeevento" not in colunas:
                conexao.execute(
                    text(
                        "ALTER TABLE evento "
                        "ADD COLUMN qtcapacidadeevento INT NULL AFTER dtfimevento"
                    )
                )

            verificacoes = {
                verificacao.get("name")
                for verificacao in inspect(engine).get_check_constraints("evento")
            }
            if "chk_evento_capacidade" not in verificacoes:
                conexao.execute(
                    text(
                        "ALTER TABLE evento "
                        "ADD CONSTRAINT chk_evento_capacidade "
                        "CHECK (qtcapacidadeevento IS NULL OR qtcapacidadeevento > 0)"
                    )
                )

            conexao.execute(
                text(
                    """
                    UPDATE evento e
                    LEFT JOIN (
                      SELECT evento_id, SUM(qtcapacidade) AS capacidade_setores
                      FROM eventosetor
                      WHERE sitsetor = 'ATIVO'
                      GROUP BY evento_id
                    ) setores ON setores.evento_id = e.evento_id
                    SET e.qtcapacidadeevento = setores.capacidade_setores
                    WHERE e.qtcapacidadeevento IS NULL
                      AND COALESCE(setores.capacidade_setores, 0) > 0
                    """
                )
            )
        logger.info("Capacidade dos eventos agendados verificada.")
    except Exception:
        logger.exception("Não foi possível preparar a capacidade dos eventos agendados")
        raise

@app.get("/health")
def health():
    banco_online = False
    try:
        with engine.connect() as conexao:
            conexao.execute(text("SELECT 1"))
        banco_online = True
    except Exception:
        logging.exception("Falha no health check do banco de dados")

    producao = APP_ENV in {"production", "prod"}
    return {
        "status": "ok" if banco_online else "degraded",
        "api": "online",
        "database": "online" if banco_online else "offline",
        "environment": "P" if producao else "D",
    }


@app.get("/")
def serve_flutter():
    return FileResponse("app/static/index.html")


@app.get("/favicon.png")
def serve_favicon():
    return FileResponse("app/static/favicon.png")

@app.get("/.well-known/assetlinks.json")
def assetlinks():
    return FileResponse("app/static/.well-known/assetlinks.json")
    
@app.get("/{full_path:path}")
def serve_flutter_routes(full_path: str):
    if (
        full_path.startswith("uploads")
        or full_path.startswith("assets")
        or full_path.startswith(".well-known")
        or full_path == "health"
        or full_path.startswith("docs")
        or full_path.startswith("redoc")
        or full_path.startswith("openapi.json")
    ):
        return JSONResponse(status_code=404, content={"detail": "Not Found"})

    return FileResponse("app/static/index.html")
