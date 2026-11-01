import unittest
import warnings
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.exc import SAWarning
from sqlalchemy.orm import Query, Session
from sqlalchemy.sql import FROM_LINTING

import importlib
import pkgutil

import app.models

for module in pkgutil.iter_modules(app.models.__path__):
    importlib.import_module(f'app.models.{module.name}')
from app.routers.entregas import listar_itens_nao_entregues


class EntregasPendentesQueryTest(unittest.TestCase):
    def test_consulta_nao_tem_produto_cartesiano(self):
        engine = create_engine('sqlite://')
        statements = []

        def capturar_consulta(query):
            with warnings.catch_warnings():
                warnings.simplefilter('error', SAWarning)
                statements.append(str(query.statement.compile(linting=FROM_LINTING)))
            return []

        with Session(engine) as db, patch.object(Query, 'all', capturar_consulta):
            self.assertEqual([], listar_itens_nao_entregues(cliente_id=1, loja_id=1, db=db))
        self.assertEqual(1, len(statements))
        self.assertIn('LEFT OUTER JOIN eventoloteglobal', statements[0])
        self.assertIn('evento.evento_id = eventoloteglobal.evento_id', statements[0])


if __name__ == '__main__':
    unittest.main()
