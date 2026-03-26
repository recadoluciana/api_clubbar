# mysql -u bitbeer_user -p bitbeer
from fastapi import FastAPI
from sqlalchemy import text
from app.database import engine, Base

# 🔥 garante que TODOS os models sejam carregados (Pais, Estado, Cidade etc.)
import app.models  # precisa existir app/models/__init__.py importando os models

#from app.routers.pais  import pais
#from app.routers.estado import estado
#from app.routers.cidade import cidade

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

app = FastAPI(title="clubbar API")

from fastapi.staticfiles import StaticFiles

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# ✅ cria as tabelas automaticamente (DEV)
@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)

#app.include_router(pais.router)
#app.include_router(estado.router)

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

# 👇 COLOCA AQUI
from fastapi.staticfiles import StaticFiles
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

@app.get("/health")
def health():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"ok": True}
