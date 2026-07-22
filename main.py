import os

from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

import app.models as app_models
from app.core.config import UPLOAD_DIR

from app.routers import cidades
from app.routers import auth
from app.routers import organizacao
from app.routers import lojas
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
from app.routers import mercadopago_webhook
from app.routers import parceiros
from app.routers import superadmin
from app.routers import stripe_webhook
from app.routers import asaas_webhook


app = FastAPI(title="clubbar API")

origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
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

    # manter por enquanto durante a transição
    "https://clubbarsite-production.up.railway.app",
    "https://clubbarcliente-production.up.railway.app",
    "https://clubbaradmin-production.up.railway.app",
    "https://bitbeer-production.up.railway.app",

    # manter por enquanto durante a transição
    "https://clubbarsite-desenvolvimento.up.railway.app",
    "https://clubbarcliente-desenvolvimento.up.railway.app",
    "https://clubbaradmin-desenvolvimento.up.railway.app",
    "https://apiclubbar-desenvolvimento.up.railway.app",
]


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(UPLOAD_DIR, exist_ok=True)

os.makedirs("app/static", exist_ok=True)
os.makedirs("app/static/assets", exist_ok=True)

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

app.mount("/assets", StaticFiles(directory="app/static/assets"), name="assets")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(cidades.router)
app.include_router(auth.router)
app.include_router(organizacao.router)
app.include_router(lojas.router)
app.include_router(produtos.router)
app.include_router(categoria.router)
app.include_router(carrinho.router)
app.include_router(compras.router)
app.include_router(pagamentos.router)
app.include_router(entregas.router)
app.include_router(eventos.router)
app.include_router(eventolotes.router)
app.include_router(usuarios.router)
app.include_router(clisenha.router)
app.include_router(clientes.router)
app.include_router(mercadopago_webhook.router)
app.include_router(parceiros.router)
app.include_router(superadmin.router)
app.include_router(stripe_webhook.router)
app.include_router(asaas_webhook.router)

@app.get("/health")
def health():
    return {"status": "ok"}


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
