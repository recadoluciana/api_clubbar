import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="clubbar API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://clubbaradmin-production.up.railway.app",
        "https://admin.clubbar.com.br",
        "https://www.clubbar.com.br",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# garante que TODOS os models sejam carregados
import app.models as app_models

from app.routers import cidades
from app.routers import auth
from app.routers import organizacao
from app.routers import lojas
from app.routers import produtos
from app.routers import categoria
from app.routers import carrinho
from app.routers import compras
from app.routers import pagamentos
from app.routers import pagbank_webhook
from app.routers import entregas
from app.routers import eventos
from app.routers import eventolotes

# cria a pasta uploads se não existir
os.makedirs("uploads", exist_ok=True)

# monta arquivos estáticos uma vez só
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.include_router(cidades.router)
app.include_router(auth.router)
app.include_router(organizacao.router)
app.include_router(lojas.router)
app.include_router(produtos.router)
app.include_router(categoria.router)
app.include_router(carrinho.router)
app.include_router(compras.router)
app.include_router(pagamentos.router)
app.include_router(pagbank_webhook.router)
app.include_router(entregas.router)
app.include_router(eventos.router)
app.include_router(eventolotes.router)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/teste-deploy")
def teste_deploy():
    return {"msg": "deploy novo funcionando"}