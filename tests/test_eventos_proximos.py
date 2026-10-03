import unittest
from datetime import datetime

from sqlalchemy.dialects import mysql

from app.routers.eventos import filtro_evento_atual_ou_proximo


class EventosProximosTest(unittest.TestCase):
    def test_filtro_mantem_evento_por_seis_horas_apos_inicio(self):
        inicio_dia = datetime(2026, 8, 5)

        sql = str(
            filtro_evento_atual_ou_proximo(inicio_dia).compile(
                dialect=mysql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )

        self.assertIn("evento.dtinicioevento >= '2026-08-04 18:00:00'", sql)


if __name__ == "__main__":
    unittest.main()
