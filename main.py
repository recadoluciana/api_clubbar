import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="clubbar API")


@app.middleware("http")
async def cors_fix(request: Request, call_next):
    if request.method == "OPTIONS":
        response = Response()
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "*"
        return response

    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

os.makedirs("/app/uploads", exist_ok=True)
os.makedirs("app/static", exist_ok=True)
os.makedirs("app/static/assets", exist_ok=True)

app.mount("/uploads", StaticFiles(directory="/app/uploads"), name="uploads")
app.mount("/assets", StaticFiles(directory="app/static/assets"), name="assets")

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


@app.get("/")
def serve_flutter():
    return FileResponse("app/static/index.html")


@app.get("/favicon.png")
def serve_favicon():
    return FileResponse("app/static/favicon.png")


@app.get("/{full_path:path}")
def serve_flutter_routes(full_path: str):
    if full_path.startswith("uploads") or full_path.startswith("assets") or full_path == "health":
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
    return FileResponse("app/static/index.html")