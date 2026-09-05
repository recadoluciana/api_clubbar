from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import text

PROJECT_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_DIR))

from dotenv import load_dotenv

load_dotenv(PROJECT_DIR / ".env", override=False)

from app.database import SessionLocal


ESTILOS = [
    "Axé", "Baião", "Bebop", "Black Music", "Bluegrass", "Blues",
    "Bossa Nova", "Brega", "Brega Funk", "Canto Coral", "Choro",
    "Clássica", "Country", "Dance", "Disco", "Drum and Bass", "Dub",
    "Dubstep", "Eletrônica", "Emo", "Fado", "Folk", "Forró",
    "Forró Eletrônico", "Forró Pé de Serra", "Frevo", "Funk Americano",
    "Funk Carioca", "Funk Melody", "Gospel", "Grunge", "Hard Rock",
    "Hardcore", "Heavy Metal", "Hip Hop", "House", "Indie", "Jazz",
    "Jovem Guarda", "K-pop", "Lambada", "Latin Pop", "Lo-fi", "Maracatu",
    "Marchinha", "Metal", "MPB", "Música Caipira", "Música Gaúcha",
    "Música Instrumental", "Pagode", "Piseiro", "Pop", "Pop Nacional",
    "Pop Internacional", "Pós-punk", "Progressivo", "Punk Rock", "R&B",
    "Rap", "Rap Nacional", "Reggae", "Reggaeton", "Rock Nacional",
    "Rock Internacional", "Salsa", "Samba", "Samba-enredo", "Samba-rock",
    "Sertanejo", "Sertanejo Raiz", "Sertanejo Universitário", "Ska", "Soul",
    "Tecnobrega", "Techno", "Trap", "Trap Nacional", "Trance", "Vaneira",
    "Xote", "Zouk",
]


def main() -> None:
    db = SessionLocal()
    try:
        for nome in ESTILOS:
            db.execute(
                text(
                    """
                    INSERT INTO estilomusical (nmestilomusical, sitestilomusical)
                    VALUES (:nome, 'ATIVO')
                    ON DUPLICATE KEY UPDATE sitestilomusical = 'ATIVO'
                    """
                ),
                {"nome": nome},
            )
        db.execute(
            text(
                """
                INSERT IGNORE INTO atracaoestilomusical (
                    atracao_id,
                    estilomusical_id
                )
                SELECT
                    a.atracao_id,
                    e.estilomusical_id
                FROM atracao AS a
                INNER JOIN estilomusical AS e
                    ON FIND_IN_SET(
                        LOWER(e.nmestilomusical),
                        LOWER(REPLACE(COALESCE(a.dsestilomusical, ''), ', ', ','))
                    ) > 0
                """
            )
        )
        db.commit()
        print(f"Estilos musicais carregados: {len(ESTILOS)}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
