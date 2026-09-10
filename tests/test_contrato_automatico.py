import asyncio
import unittest
from hashlib import sha256
from sqlalchemy import BigInteger, create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session
from fastapi import HTTPException
from starlette.requests import Request
from app.models.titularfinanceiro import TitularFinanceiro
from app.models.taxapadrao import TaxaPadrao
from app.services.contrato_automatico import (
    Cidade, Estado, ContratoPadrao, LeadParceiro, LeadEstabelecimento,
    LeadEstabelecimentoContrato, garantir_contrato, preencher_contrato_portal,
)
from app.routers.contratolead import aceitar_contrato


@compiles(BigInteger, "sqlite")
def sqlite_integer(type_, compiler, **kw):
    return "INTEGER"


class ContratoAutomaticoTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        for model in [Estado, Cidade, LeadParceiro, LeadEstabelecimento, ContratoPadrao, TaxaPadrao, LeadEstabelecimentoContrato]:
            model.__table__.create(self.engine)
        self.db = Session(self.engine)
        self.db.add_all([
            Estado(estado_id=1, pais_id=1, sgestado="MG", nmestado="Minas Gerais"),
            Cidade(cidade_id=1, pais_id=1, estado_id=1, nmcidade="Teste"),
            LeadParceiro(leadparceiro_id=1, nmresponsavel="Pessoa", telefone="11999990000", email="teste@example.com"),
            ContratoPadrao(contratopadrao_id=1, versao="v1", titulo="Contrato", conteudomodelo="Clubbar: {{NOME_ESTABELECIMENTO}}; {{CPF_CNPJ}}; {{TAXA_PRODUTOS}}", vrimplantacao=10, sitcontrato="ATIVO"),
            TaxaPadrao(taxapadrao_id=1, nrversao=1, pctaxaproduto=5, pctaxaingresso=10, vrtaxaminimaingresso=2, sittaxapadrao="VIGENTE"),
        ])
        self.est = LeadEstabelecimento(leadestabelecimento_id=1, leadparceiro_id=1, nmestabelecimento="Clubbar", tipo="BAR", estado_id=1, cidade_id=1)
        self.db.add(self.est)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_cria_rascunho_sem_documento_e_nao_duplica(self):
        item = garantir_contrato(self.db, self.est)
        self.assertEqual(item.status, "RASCUNHO")
        self.assertIn("[CPF/CNPJ a preencher]", item.conteudocontrato)
        self.assertEqual(garantir_contrato(self.db, self.est).leadestabelecimentocontrato_id, item.leadestabelecimentocontrato_id)
        self.assertEqual(self.db.query(LeadEstabelecimentoContrato).count(), 1)

    def test_preenche_sem_alterar_clausulas_e_preserva_aceito(self):
        item = garantir_contrato(self.db, self.est)
        item = preencher_contrato_portal(self.db, 1, item.leadestabelecimentocontrato_id, "123.456.789-01", "Minha empresa")
        self.assertTrue(item.conteudocontrato.startswith("Clubbar: Minha empresa; 12345678901; 5.00"))
        self.assertEqual(item.status, "ENVIADO")
        self.assertEqual(item.hashdocumento, sha256(item.conteudocontrato.encode()).hexdigest())
        req = Request({"type": "http", "client": ("127.0.0.1", 123)})
        asyncio.run(aceitar_contrato(item.leadestabelecimentocontrato_id, req, self.db.get(LeadParceiro, 1), self.db))
        frozen = item.conteudocontrato
        with self.assertRaises(HTTPException) as error:
            preencher_contrato_portal(self.db, 1, item.leadestabelecimentocontrato_id, "12345678901", "Outro")
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(garantir_contrato(self.db, self.est).conteudocontrato, frozen)

    def test_nao_permite_outro_lead_nem_assinatura_de_rascunho(self):
        item = garantir_contrato(self.db, self.est)
        with self.assertRaises(HTTPException) as error:
            preencher_contrato_portal(self.db, 2, item.leadestabelecimentocontrato_id, "12345678901", "Outro")
        self.assertEqual(error.exception.status_code, 404)
        req = Request({"type": "http", "client": ("127.0.0.1", 123)})
        with self.assertRaises(HTTPException) as error:
            asyncio.run(aceitar_contrato(item.leadestabelecimentocontrato_id, req, self.db.get(LeadParceiro, 1), self.db))
        self.assertEqual(error.exception.status_code, 422)

    def test_documento_incompleto_nao_finaliza(self):
        item = garantir_contrato(self.db, self.est)
        with self.assertRaises(HTTPException):
            preencher_contrato_portal(self.db, 1, item.leadestabelecimentocontrato_id, "123", "Outro")
        self.assertEqual(item.status, "RASCUNHO")

    def test_cadastro_portal_disponibiliza_contrato_na_mesma_transacao(self):
        from app.routers.portalparceiro import cadastrar_estabelecimento
        from app.schemas.portalparceiro import PortalEstabelecimentoCreate
        dados = PortalEstabelecimentoCreate(nmestabelecimento="Novo bar", tipo="BAR", estado_id=1, cidade_id=1)
        resultado = cadastrar_estabelecimento(dados, self.db.get(LeadParceiro, 1), self.db)
        contrato = self.db.query(LeadEstabelecimentoContrato).filter_by(
            leadestabelecimento_id=resultado["leadestabelecimento_id"]).one()
        self.assertEqual(contrato.status, "RASCUNHO")
        self.assertTrue(contrato.conteudocontrato)
