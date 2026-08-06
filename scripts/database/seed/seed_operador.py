import os

from app.core.security import hash_senha
from app.database import SessionLocal
from app.models.operador import Operador


def main() -> None:
    email = os.environ["CLUBBAR_ADMIN_EMAIL"].lower().strip()
    senha = os.environ["CLUBBAR_ADMIN_PASSWORD"]
    nome = os.getenv("CLUBBAR_ADMIN_NAME", "Administrador Clubbar").strip()
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
