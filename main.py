import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="clubbar API")

# 🔥 CORREÇÃO DEFINITIVA PARA PREFLIGHT (FLUTTER WEB)
@app.middleware("http")
async def cors_fix(request: Request, call_next):
    if request.method == "OPTIONS":
        return JSONResponse(content={"ok": True})
    response = await call_next(request)
    return response

# 🔥 CORS AJUSTADO PARA WEB + MOBILE + PRODUÇÃO
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://clubbaradmin-production.up.railway.app",
        "https://admin.clubbar.com.br",
        "https://www.clubbar.com.br",

        # DEV
        "http://localhost:50945",
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:50945",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# 🔥 IMPORTA TODOS OS MODELS
import app.models as app_models

# 🔥 IMPORTA ROTAS
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

# 🔥 GARANTE PASTA DE UPLOAD
os.makedirs("uploads", exist_ok=True)

# 🔥 SERVE IMAGENS
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# 🔥 REGISTRA ROTAS
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

# 🔥 HEALTH CHECK
@app.get("/health")
def health():
    return {"status": "ok"}

# 🔥 TESTE DE DEPLOY
@app.get("/teste-deploy")
def teste_deploy():
    return {"msg": "deploy novo funcionando"}