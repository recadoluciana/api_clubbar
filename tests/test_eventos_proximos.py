import unittest
from datetime import datetime

from sqlalchemy.dialects import mysql

from app.routers.eventos import filtro_evento_atual_ou_proximo


class EventosProximosTest(unittest.TestCase):
    def test_filtro_considera_inicio_futuro_ou_fim_futuro(self):
        inicio_dia = datetime(2026, 8, 5)

        sql = str(
            filtro_evento_atual_ou_proximo(inicio_dia).compile(
                dialect=mysql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )

        self.assertIn("evento.dtinicioevento >= '2026-08-05 00:00:00'", sql)
        self.assertIn("evento.dtfimevento >= '2026-08-05 00:00:00'", sql)
        self.assertIn(" OR ", sql)


if __name__ == "__main__":
    unittest.main()
