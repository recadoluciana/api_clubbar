import os
import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

import app.models as app_models
from app.core.config import APP_ENV, UPLOAD_DIR
from app.database import engine
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
from app.routers import cardapio_padrao
from app.routers import auditoria
from app.routers import eventosetores
from app.routers import eventomodelos


app = FastAPI(title="clubbar API")

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
    "https://clubbarcliente-desenvolvimento.up.railway.app",

    "https://clubbar.com.br",
    "https://www.clubbar.com.br",
    "https://app.clubbar.com.br",
    "https://admin.clubbar.com.br",
    "https://api.clubbar.com.br",
    "https://parceiro.clubbar.com.br",

    # manter por enquanto durante a transição
    "https://clubbarsite-production.up.railway.app",
    "https://clubbarcliente-production.up.railway.app",
    "https://clubbaradmin-production.up.railway.app",
    "https://clubbarpartner-production.up.railway.app",
    "https://bitbeer-production.up.railway.app",

    # manter por enquanto durante a transição
    "https://clubbarsite-desenvolvimento.up.railway.app",
    "https://clubbarcliente-desenvolvimento.up.railway.app",
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
app.include_router(cardapio_padrao.router)
app.include_router(auditoria.router)
app.include_router(eventosetores.router)

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
