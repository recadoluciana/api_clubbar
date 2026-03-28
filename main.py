from fastapi import FastAPI

app = FastAPI(title="clubbar API")

from app.routers import auth

app.include_router(auth.router)

@app.get("/health")
def health():
    return {"status": "ok"}