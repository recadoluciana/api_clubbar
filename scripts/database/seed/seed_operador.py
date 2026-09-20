import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv


PROJECT_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_DIR))

load_dotenv(PROJECT_DIR / ".env", override=False)

from app.core.security import hash_senha
from app.database import SessionLocal
from app.models.operador import Operador
from app.core.config import APP_ENV
from sqlalchemy import text


SOCIOS_DESENVOLVIMENTO = (
    ("Luciana Corrêa", "recadoluciana@gmail.com"),
    ("Tricia Murad", "triciamurad@gmail.com"),
    ("Adilson", "adilson.datascience@gmail.com"),
)


def seed(db, *, recriar: bool = False, allow_production: bool = False) -> None:
    is_production = APP_ENV in {"prod", "production"}
    if APP_ENV not in {"dev", "development", "prod", "production"}:
        raise RuntimeError(f"Seed bloqueado para APP_ENV={APP_ENV!r}.")
    if is_production and not allow_production:
        raise RuntimeError("Em produção, use --allow-production para criar os operadores.")
    expected_database = "clubbar_prod" if is_production else "clubbar_dev"
    if db.execute(text("SELECT DATABASE()")).scalar() != expected_database:
        raise RuntimeError(f"Seed bloqueado: a base precisa ser {expected_database}.")
    if recriar:
        # DELETE preserves auto-increment and lets audit foreign keys become NULL.
        db.query(Operador).delete(synchronize_session=False)
    for nome, email in SOCIOS_DESENVOLVIMENTO:
        operador = db.query(Operador).filter(Operador.emailoperador == email).first()
        if operador is None:
            operador = Operador(emailoperador=email)
            db.add(operador)
        operador.nmoperador = nome
        operador.senhahashoperador = hash_senha("101010")
        operador.perfil = "ADMIN"
        operador.sitoperador = "ATIVO"
    db.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Cria os três sócios no desenvolvimento.")
    parser.add_argument("--recriar", action="store_true", help="Apaga os operadores atuais e recria somente os três sócios.")
    parser.add_argument(
        "--allow-production",
        action="store_true",
        help="Autoriza explicitamente a criação dos operadores na produção.",
    )
    args = parser.parse_args()
    with SessionLocal() as db:
        seed(db, recriar=args.recriar, allow_production=args.allow_production)
        for nome, email in SOCIOS_DESENVOLVIMENTO:
            print(f"Sócio disponível: {nome} <{email}> — ADMIN / ATIVO")


if __name__ == "__main__":
    main()
