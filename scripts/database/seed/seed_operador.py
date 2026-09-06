import os
import sys
from pathlib import Path

from dotenv import load_dotenv


PROJECT_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_DIR))

load_dotenv(PROJECT_DIR / ".env", override=False)

from app.core.security import hash_senha
from app.database import SessionLocal
from app.models.operador import Operador


def main() -> None:
    email = os.getenv("CLUBBAR_ADMIN_EMAIL", "suporte@clubbar.com.br").lower().strip()
    senha = os.environ["CLUBBAR_ADMIN_PASSWORD"]
    nome = os.getenv("CLUBBAR_ADMIN_NAME", "Suporte Clubbar").strip()
    with SessionLocal() as db:
        operador = db.query(Operador).filter(Operador.emailoperador == email).first()
        if operador is None:
            operador = Operador(nmoperador=nome, emailoperador=email, perfil="ADMIN")
            db.add(operador)
        operador.nmoperador = nome
        operador.senhahashoperador = hash_senha(senha)
        operador.sitoperador = "ATIVO"
        db.commit()
        print(f"Operador Clubbar disponivel: {email}")


if __name__ == "__main__":
    main()
