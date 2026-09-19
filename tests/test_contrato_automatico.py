import asyncio
import unittest
from unittest.mock import patch
from hashlib import sha256
from sqlalchemy import BigInteger, create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session
from fastapi import HTTPException
from starlette.requests import Request
from app.models.titularfinanceiro import TitularFinanceiro
from app.models.leadmensagem import LeadMensagem
from app.models.loja import Loja
from app.models.organizacao import Organizacao
from app.models.taxapadrao import TaxaPadrao
from app.services.contrato_automatico import (
    Cidade, Estado, ContratoPadrao, LeadParceiro, LeadEstabelecimento,
    LeadEstabelecimentoContrato, garantir_contrato, preencher_contrato_portal,
)
from app.routers.contratolead import EnderecoContratoPortal, RetificacaoContratoIn, aceitar_contrato, atualizar_endereco_contrato_portal, criar_retificacao, cancelar_retificacao, previsualizar_retificacao


@compiles(BigInteger, "sqlite")
def sqlite_integer(type_, compiler, **kw):
    return "INTEGER"


class ContratoAutomaticoTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        for model in [Estado, Cidade, LeadParceiro, Organizacao, TitularFinanceiro, LeadEstabelecimento, ContratoPadrao, TaxaPadrao, LeadEstabelecimentoContrato, LeadMensagem, Loja]:
            model.__table__.create(self.engine)
        self.db = Session(self.engine)
        self.db.add_all([
            Estado(estado_id=1, pais_id=1, sgestado="MG", nmestado="Minas Gerais"),
            Cidade(cidade_id=1, pais_id=1, estado_id=1, nmcidade="Teste"),
            LeadParceiro(leadparceiro_id=1, nmresponsavel="Pessoa", telefone="11999990000", email="teste@example.com"),
            ContratoPadrao(contratopadrao_id=1, versao="v1", titulo="Contrato", conteudomodelo="Clubbar: {{NOME_ESTABELECIMENTO}}; {{CPF_CNPJ}}; {{TAXA_PRODUTOS}}; {{ENDERECO}}", vrimplantacao=10, sitcontrato="ATIVO"),
            TaxaPadrao(taxapadrao_id=1, nrversao=1, pctaxaproduto=5, pctaxaingresso=10, vrtaxaminimaingresso=2.99, sittaxapadrao="VIGENTE"),
        ])
        self.est = LeadEstabelecimento(leadestabelecimento_id=1, leadparceiro_id=1, nmestabelecimento="Clubbar", tipo="BAR", estado_id=1, cidade_id=1)
        self.db.add(self.est)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def completar_endereco(self, contrato_id):
        dados = EnderecoContratoPortal(
            cep="30130000", endereco="Rua da Bahia", numero="100",
            bairro="Centro", estado_id=1, cidade_id=1,
        )
        return atualizar_endereco_contrato_portal(
            contrato_id, dados, self.db.get(LeadParceiro, 1), self.db,
        )

    def contrato_aceito(self):
        item = garantir_contrato(self.db, self.est)
        preencher_contrato_portal(self.db, 1, item.leadestabelecimentocontrato_id, "12345678901", "Minha empresa")
        self.completar_endereco(item.leadestabelecimentocontrato_id)
        req = Request({"type": "http", "client": ("127.0.0.1", 123)})
        asyncio.run(aceitar_contrato(item.leadestabelecimentocontrato_id, req, self.db.get(LeadParceiro, 1), self.db))
        return item

    def dados_retificacao(self, **alteracoes):
        dados = dict(
            motivo="Correção dos dados informados na assinatura original.",
            cpfcnpj="12345678901", nmrazaosocial="Minha empresa",
            cep="30130000", endereco="Rua da Bahia", numero="200",
            bairro="Centro", estado_id=1, cidade_id=1,
            vrtaxaprod="6.00", vrtaxaing="10.00", vrtaxaminimaingresso="2.00",
        )
        dados.update(alteracoes)
        return RetificacaoContratoIn(**dados)

    def test_retificacao_preserva_original_e_so_aplica_apos_novo_aceite(self):
        original = self.contrato_aceito()
        texto_original, hash_original = original.conteudocontrato, original.hashdocumento
        dados = self.dados_retificacao()
        previa = previsualizar_retificacao(1, dados, {}, self.db)
        self.assertIn("200", previa["conteudocontrato"])
        termo = criar_retificacao(1, dados, {}, self.db)
        self.assertEqual(termo["nrretificacao"], 1)
        self.assertEqual(termo["contratoorigem_id"], original.leadestabelecimentocontrato_id)
        self.assertEqual(self.est.numero, "100")
        self.assertEqual(float(self.est.vrtaxaprod), 5)
        with self.assertRaises(HTTPException) as error:
            criar_retificacao(1, dados, {}, self.db)
        self.assertEqual(error.exception.status_code, 409)
        req = Request({"type": "http", "client": ("127.0.0.1", 123)})
        asyncio.run(aceitar_contrato(termo["leadestabelecimentocontrato_id"], req, self.db.get(LeadParceiro, 1), self.db))
        self.assertEqual(self.est.numero, "200")
        self.assertEqual(float(self.est.vrtaxaprod), 6)
        self.assertEqual(original.conteudocontrato, texto_original)
        self.assertEqual(original.hashdocumento, hash_original)
        self.assertEqual(original.status, "ACEITO")
        self.assertEqual(self.db.get(LeadEstabelecimentoContrato, termo["leadestabelecimentocontrato_id"]).status, "ACEITO")

    def test_cpf_cnpj_alterado_exige_confirmacao_mesma_parte(self):
        self.contrato_aceito()
        with self.assertRaises(HTTPException) as error:
            previsualizar_retificacao(1, self.dados_retificacao(cpfcnpj="98765432100"), {}, self.db)
        self.assertEqual(error.exception.status_code, 422)
        termo = criar_retificacao(1, self.dados_retificacao(cpfcnpj="98765432100", confirma_mesma_parte=True), {}, self.db)
        self.assertEqual(termo["cpfcnpjcontratante"], "98765432100")
        cancelar_retificacao(termo["leadestabelecimentocontrato_id"], {}, self.db)
        self.assertEqual(self.est.cpfcnpj, None)

    def test_retificacao_cancelada_nao_pode_ser_assinada(self):
        self.contrato_aceito()
        termo = criar_retificacao(1, self.dados_retificacao(), {}, self.db)
        cancelar_retificacao(termo["leadestabelecimentocontrato_id"], {}, self.db)
        req = Request({"type": "http", "client": ("127.0.0.1", 123)})
        with self.assertRaises(HTTPException) as error:
            asyncio.run(aceitar_contrato(termo["leadestabelecimentocontrato_id"], req, self.db.get(LeadParceiro, 1), self.db))
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(self.est.numero, "100")

    def test_cria_rascunho_sem_documento_e_nao_duplica(self):
        item = garantir_contrato(self.db, self.est)
        self.assertEqual(item.status, "RASCUNHO")
        self.assertEqual(float(item.vrtaxaminimaingresso), 2.99)
        self.assertEqual(float(self.est.vrtaxaminimaingresso), 2.99)
        self.assertIn("[CPF/CNPJ a preencher]", item.conteudocontrato)
        self.assertEqual(garantir_contrato(self.db, self.est).leadestabelecimentocontrato_id, item.leadestabelecimentocontrato_id)
        self.assertEqual(self.db.query(LeadEstabelecimentoContrato).count(), 1)

    def test_formata_atividade_e_modalidade_de_venda_no_contrato(self):
        self.est.tipo = "CASA_NOTURNA"
        self.est.tipovenda = "AMBOS"
        modelo = self.db.get(ContratoPadrao, 1)
        modelo.conteudomodelo = (
            "Atividade: {{ATIVIDADE}}\n"
            "Modalidade de venda: {{MODALIDADE_VENDA}}"
        )
        self.db.commit()

        item = garantir_contrato(self.db, self.est)

        self.assertIn("Atividade: Casa Noturna", item.conteudocontrato)
        self.assertIn(
            "Modalidade de venda: Venda de produtos e ingressos",
            item.conteudocontrato,
        )
        self.assertNotIn("CASA_NOTURNA", item.conteudocontrato)
        self.assertNotIn("AMBOS", item.conteudocontrato)

    def test_preenche_sem_alterar_clausulas_e_preserva_aceito(self):
        item = garantir_contrato(self.db, self.est)
        item = preencher_contrato_portal(self.db, 1, item.leadestabelecimentocontrato_id, "123.456.789-01", "Minha empresa")
        self.assertTrue(item.conteudocontrato.startswith("Clubbar: Minha empresa; 12345678901; 5.00"))
        self.assertEqual(item.status, "ENVIADO")
        self.assertEqual(item.hashdocumento, sha256(item.conteudocontrato.encode()).hexdigest())
        req = Request({"type": "http", "client": ("127.0.0.1", 123)})
        with self.assertRaises(HTTPException) as error:
            asyncio.run(aceitar_contrato(item.leadestabelecimentocontrato_id, req, self.db.get(LeadParceiro, 1), self.db))
        self.assertEqual(error.exception.status_code, 422)
        self.assertIn("CEP", error.exception.detail)
        self.completar_endereco(item.leadestabelecimentocontrato_id)
        self.assertIn("Rua da Bahia, 100", item.conteudocontrato)
        self.assertNotIn("não informado", item.conteudocontrato)
        self.assertEqual(item.hashdocumento, sha256(item.conteudocontrato.encode()).hexdigest())
        asyncio.run(aceitar_contrato(item.leadestabelecimentocontrato_id, req, self.db.get(LeadParceiro, 1), self.db))
        frozen = item.conteudocontrato
        with self.assertRaises(HTTPException) as error:
            preencher_contrato_portal(self.db, 1, item.leadestabelecimentocontrato_id, "12345678901", "Outro")
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(garantir_contrato(self.db, self.est).conteudocontrato, frozen)
        with self.assertRaises(HTTPException) as error:
            self.completar_endereco(item.leadestabelecimentocontrato_id)
        self.assertEqual(error.exception.status_code, 409)

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

    def test_endereco_so_pode_ser_corrigido_pelo_proprio_lead(self):
        item = garantir_contrato(self.db, self.est)
        dados = EnderecoContratoPortal(
            cep="30130000", endereco="Rua da Bahia", numero="100",
            bairro="Centro", estado_id=1, cidade_id=1,
        )
        outro_lead = LeadParceiro(leadparceiro_id=2, nmresponsavel="Outro", telefone="11988880000", email="outro@example.com")
        self.db.add(outro_lead)
        self.db.commit()
        with self.assertRaises(HTTPException) as error:
            atualizar_endereco_contrato_portal(item.leadestabelecimentocontrato_id, dados, outro_lead, self.db)
        self.assertEqual(error.exception.status_code, 404)
        self.assertIsNone(self.est.endereco)

    def test_assinatura_rejeita_endereco_divergente_do_contrato(self):
        item = garantir_contrato(self.db, self.est)
        preencher_contrato_portal(self.db, 1, item.leadestabelecimentocontrato_id, "12345678901", "Minha empresa")
        self.completar_endereco(item.leadestabelecimentocontrato_id)
        self.est.numero = "200"
        self.db.commit()
        req = Request({"type": "http", "client": ("127.0.0.1", 123)})
        with self.assertRaises(HTTPException) as error:
            asyncio.run(aceitar_contrato(item.leadestabelecimentocontrato_id, req, self.db.get(LeadParceiro, 1), self.db))
        self.assertEqual(error.exception.status_code, 422)
        self.assertEqual(item.status, "ENVIADO")

    def test_cadastro_portal_disponibiliza_contrato_na_mesma_transacao(self):
        from app.routers.portalparceiro import cadastrar_estabelecimento
        from app.schemas.portalparceiro import PortalEstabelecimentoCreate
        dados = PortalEstabelecimentoCreate(nmestabelecimento="Novo bar", tipo="BAR", estado_id=1, cidade_id=1, cep="30130000", endereco="Rua da Bahia", numero="100", bairro="Centro")
        with patch("app.routers.portalparceiro.validar_cep_lead"):
            resultado = cadastrar_estabelecimento(dados, self.db.get(LeadParceiro, 1), self.db)
        contrato = self.db.query(LeadEstabelecimentoContrato).filter_by(
            leadestabelecimento_id=resultado["leadestabelecimento_id"]).one()
        self.assertEqual(contrato.status, "RASCUNHO")
        self.assertTrue(contrato.conteudocontrato)
