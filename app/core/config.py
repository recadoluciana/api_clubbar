import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

JWT_SECRET = os.getenv("JWT_SECRET", "change-me")
JWT_EXPIRES_MIN = int(os.getenv("JWT_EXPIRES_MIN", "10080"))

UPLOAD_BASE = "/app/uploads"

UPLOAD_PRODUTOS = os.path.join(UPLOAD_BASE, "produtos")
UPLOAD_LOJAS = os.path.join(UPLOAD_BASE, "lojas")
UPLOAD_EVENTOS = os.path.join(UPLOAD_BASE, "eventos")

os.makedirs(UPLOAD_PRODUTOS, exist_ok=True)
os.makedirs(UPLOAD_LOJAS, exist_ok=True)
os.makedirs(UPLOAD_EVENTOS, exist_ok=True)