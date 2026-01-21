from fastapi import FastAPI
from sqlalchemy import text

from app.database import engine
from app.routers.auth  import router as auth_router
from app.routers.lojas import router as lojas_router
from app.routers.produtos import router as produtos_router
from app.routers.categoria import router as categoria_router
from app.routers.pagamento_retorno import router as pagamento_retorno_router
from app.routers import carrinho

from app.routers.pagamentos import router as pagamentos_router
from app.routers.pagbank_webhook import router as pagbank_webhook_router

app = FastAPI(title="BitBeer API")

app.include_router(auth_router)
app.include_router(lojas_router)
app.include_router(produtos_router)
app.include_router(categoria_router)                                                                    
app.include_router(carrinho.router)

app.include_router(pagamentos_router)
app.include_router(pagbank_webhook_router)
app.include_router(pagamento_retorno_router)

@app.get("/health")
def health():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"ok": True}
