import asyncio
import unittest
from unittest.mock import patch

import main  # Registra os modelos relacionados para o mapeamento do SQLAlchemy.
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.models.titularfinanceiro import TitularFinanceiro
from app.routers.titularfinanceiro import TitularFinanceiroIn, criar_titular, salvar


class TitularPorOrganizacaoTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        with self.engine.begin() as conexao:
            conexao.execute(text('''
                CREATE TABLE titularfinanceiro (
                    titularfinanceiro_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    organizacao_id INTEGER NOT NULL, tipotitular TEXT NOT NULL,
                    cpfcnpj TEXT NOT NULL, nmrazaosocial TEXT NOT NULL,
                    nmfantasia TEXT, dtnascimento DATE, email TEXT NOT NULL,
                    telefone TEXT NOT NULL, cep TEXT NOT NULL, endereco TEXT NOT NULL,
                    numero TEXT NOT NULL, complemento TEXT, bairro TEXT NOT NULL,
                    cidade_id INTEGER NOT NULL, estado_id INTEGER NOT NULL,
                    vrfaturamentomensal NUMERIC NOT NULL, asaas_account_id TEXT UNIQUE,
                    asaas_wallet_id TEXT UNIQUE, asaas_api_key_criptografada TEXT,
                    status_asaas TEXT NOT NULL DEFAULT 'NAO_INICIADO',
                    sittitular TEXT NOT NULL DEFAULT 'ATIVO', onboarding_url TEXT,
                    dtultimaverificacao DATETIME, dtcriacao DATETIME DEFAULT CURRENT_TIMESTAMP,
                    dtultatu DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (organizacao_id, cpfcnpj)
                )
            '''))
        self.db = Session(self.engine, expire_on_commit=False)
        self.escopo = patch('app.routers.titularfinanceiro._validar_escopo')
        self.escopo.start()

    def tearDown(self):
        self.escopo.stop()
        self.db.close()
        self.engine.dispose()

    def dados(self, organizacao_id, nome='Titular Teste'):
        return TitularFinanceiroIn(
            organizacao_id=organizacao_id, tipotitular='PJ', cpfcnpj='11222333000181',
            nmrazaosocial=nome, email='titular@example.com', telefone='11999999999',
            cep='30130000', endereco='Rua Teste', numero='1', bairro='Centro',
            cidade_id=1, estado_id=1, vrfaturamentomensal=1000,
        )

    def test_cria_cadastros_independentes_para_o_mesmo_documento(self):
        primeiro = criar_titular(1, self.dados(1), db=self.db, payload={})
        segundo = criar_titular(2, self.dados(2), db=self.db, payload={})
        self.assertNotEqual(primeiro['titularfinanceiro_id'], segundo['titularfinanceiro_id'])
        self.assertEqual([primeiro['organizacao_id'], segundo['organizacao_id']], [1, 2])
        with self.assertRaises(HTTPException) as erro:
            criar_titular(1, self.dados(1), db=self.db, payload={})
        self.assertEqual(erro.exception.status_code, 409)

    def test_salvar_nao_edita_titular_da_outra_organizacao(self):
        primeiro = criar_titular(1, self.dados(1), db=self.db, payload={})
        with patch('app.routers.titularfinanceiro._resolver_titular', return_value=(None, None)):
            segundo = asyncio.run(salvar(2, self.dados(2, 'Outro cadastro'), db=self.db, payload={}))
        self.assertNotEqual(primeiro['titularfinanceiro_id'], segundo['titularfinanceiro_id'])
        original = self.db.get(TitularFinanceiro, primeiro['titularfinanceiro_id'])
        self.assertEqual(original.nmrazaosocial, 'Titular Teste')
        self.assertEqual(original.organizacao_id, 1)


if __name__ == '__main__':
    unittest.main()
