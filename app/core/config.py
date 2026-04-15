import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

JWT_SECRET = os.getenv("JWT_SECRET", "change-me")
JWT_EXPIRES_MIN = int(os.getenv("JWT_EXPIRES_MIN", "10080"))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

UPLOAD_DIR = os.getenv("UPLOAD_DIR", os.path.join(BASE_DIR, "uploads"))
UPLOAD_PRODUTOS = os.path.join(UPLOAD_DIR, "produtos")
UPLOAD_LOJAS = os.path.join(UPLOAD_DIR, "lojas")
UPLOAD_EVENTOS = os.path.join(UPLOAD_DIR, "eventos")

os.makedirs(UPLOAD_PRODUTOS, exist_ok=True)
os.makedirs(UPLOAD_LOJAS, exist_ok=True)
os.makedirs(UPLOAD_EVENTOS, exist_ok=True)