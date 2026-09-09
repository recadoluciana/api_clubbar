from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text

PROJECT_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_DIR))
load_dotenv(PROJECT_DIR / ".env", override=False)

from app.database import SessionLocal


def main() -> None:
    db = SessionLocal()
    try:
        db.execute(text("""
            INSERT INTO taxapadrao
              (nrversao, pctaxaproduto, pctaxaingresso, vrtaxaminimaingresso,
               sittaxapadrao, dtiniciovigencia)
            VALUES (1, 5.00, 10.00, 2.99, 'VIGENTE', CURRENT_TIMESTAMP)
            ON DUPLICATE KEY UPDATE nrversao = nrversao
        """))
        db.commit()
        print("Taxa padrão versão 1 disponível.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
