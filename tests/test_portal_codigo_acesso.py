import unittest
import main  # Registra todos os modelos relacionados antes de configurar os mapeamentos.
from datetime import datetime, timedelta
from unittest.mock import patch
from fastapi import HTTPException
from sqlalchemy import create_engine, Integer
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models.leadparceiro import LeadParceiro
from app.models.leadestabelecimento import LeadEstabelecimento
from app.models.leadacesso import LeadAcesso, LeadCodigoAcesso
from app.models.estado import Estado
from app.models.cidade import Cidade
from app.routers.portalparceiro import solicitar_codigo_portal, confirmar_codigo_portal
from app.schemas.portalparceiro import PortalSolicitarCodigo, PortalConfirmarCodigo


class PortalCodigoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tipos = [(LeadCodigoAcesso.__table__.c.id, LeadCodigoAcesso.__table__.c.id.type), (LeadAcesso.__table__.c.leadacesso_id, LeadAcesso.__table__.c.leadacesso_id.type)]
        for coluna, _ in cls.tipos: coluna.type = Integer()

    @classmethod
    def tearDownClass(cls):
        for coluna, tipo in cls.tipos: coluna.type = tipo

    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        # Simula a base legada antes da migração, que pode conter documentos duplicados.
        restricao = next(c for c in LeadEstabelecimento.__table__.constraints if c.name == "uk_leadestabelecimento_cpfcnpj")
        LeadEstabelecimento.__table__.constraints.remove(restricao)
        try:
            Base.metadata.create_all(self.engine, tables=[Estado.__table__, Cidade.__table__, LeadParceiro.__table__, LeadEstabelecimento.__table__, LeadAcesso.__table__, LeadCodigoAcesso.__table__])
        finally:
            LeadEstabelecimento.__table__.constraints.add(restricao)
        self.db = sessionmaker(bind=self.engine)()
        self.db.add(LeadParceiro(leadparceiro_id=1,nmresponsavel='Teste',nmorganizacao='Empresa',email='teste@example.com',telefone='11999999999'))
        self.db.add(LeadEstabelecimento(leadestabelecimento_id=1,leadparceiro_id=1,nmestabelecimento='Teste',tipo='BAR',cpfcnpj='52998224725'))
        self.db.commit()
        self.enviado = []
        self.patcher = patch('app.routers.portalparceiro.enviar_codigo_acesso_portal',side_effect=lambda email,codigo:self.enviado.append((email,codigo)))
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop(); self.db.close(); self.engine.dispose()

    def solicitar(self):
        return solicitar_codigo_portal(PortalSolicitarCodigo(documento='529.982.247-25'), self.db)

    def confirmar(self,codigo):
        return confirmar_codigo_portal(PortalConfirmarCodigo(documento='52998224725',codigo=codigo), self.db)

    def test_codigo_valido_somente_uma_vez(self):
        self.solicitar()
        self.assertEqual(self.enviado[0][0], 'teste@example.com')
        codigo = self.enviado[0][1]
        self.assertTrue(self.confirmar(codigo)['acesso'])
        with self.assertRaises(HTTPException): self.confirmar(codigo)

    def test_cnpj_alfanumerico_usa_o_email_da_conta(self):
        self.db.add(LeadEstabelecimento(leadestabelecimento_id=2, leadparceiro_id=1, nmestabelecimento='Produtora', tipo='PRODUTOR_EVENTOS', cpfcnpj='12ABC34501DE35'))
        self.db.commit()
        solicitar_codigo_portal(PortalSolicitarCodigo(documento='12.ABC.345/01DE-35'), self.db)
        self.assertEqual(self.enviado[0][0], 'teste@example.com')
        result = confirmar_codigo_portal(PortalConfirmarCodigo(documento='12ABC34501DE35', codigo=self.enviado[0][1]), self.db)
        self.assertTrue(result['acesso'])

    def test_documento_em_duas_contas_nao_faz_escolha_arbitraria(self):
        self.db.add(LeadParceiro(leadparceiro_id=2,nmresponsavel='Outro',nmorganizacao='Outra',email='outro@example.com',telefone='11999999999'))
        self.db.add(LeadEstabelecimento(leadestabelecimento_id=2,leadparceiro_id=2,nmestabelecimento='Outro',tipo='BAR',cpfcnpj='52998224725'))
        self.db.commit()
        resposta = self.solicitar()
        self.assertTrue(resposta["requer_email"])
        self.assertEqual(self.enviado, [])
        solicitar_codigo_portal(PortalSolicitarCodigo(documento="52998224725", email="outro@example.com"), self.db)
        self.assertEqual([email for email, _ in self.enviado], ["outro@example.com"])
        codigo = self.enviado[0][1]
        with self.assertRaises(HTTPException):
            confirmar_codigo_portal(PortalConfirmarCodigo(documento="52998224725", email="teste@example.com", codigo=codigo), self.db)
        resultado = confirmar_codigo_portal(PortalConfirmarCodigo(documento="52998224725", email="outro@example.com", codigo=codigo), self.db)
        token = resultado["acesso"]
        self.assertEqual(self.db.query(LeadAcesso).filter_by(tokenhash=__import__("hashlib").sha256(token.encode()).hexdigest()).one().leadparceiro_id, 2)

    def test_email_nao_cadastrado_nao_envia_codigo(self):
        resultado = solicitar_codigo_portal(PortalSolicitarCodigo(documento="52998224725", email="ausente@example.com"), self.db)
        self.assertNotIn("requer_email", resultado)
        self.assertEqual(self.enviado, [])

    def test_mesmo_email_e_documento_em_duas_contas_nao_seleciona_uma(self):
        self.db.add(LeadParceiro(leadparceiro_id=2,nmresponsavel="Outro",nmorganizacao="Outra",email="teste@example.com",telefone="11999999999"))
        self.db.add(LeadEstabelecimento(leadestabelecimento_id=2,leadparceiro_id=2,nmestabelecimento="Outro",tipo="BAR",cpfcnpj="52998224725"))
        self.db.commit()
        solicitar_codigo_portal(PortalSolicitarCodigo(documento="52998224725", email="teste@example.com"), self.db)
        self.assertEqual(self.enviado, [])

    def test_codigo_expirado(self):
        self.solicitar(); codigo = self.enviado[0][1]
        registro = self.db.query(LeadCodigoAcesso).first(); registro.expiracao = datetime.now()-timedelta(seconds=1); self.db.commit()
        with self.assertRaises(HTTPException): self.confirmar(codigo)

    def test_cinco_tentativas_invalidam_codigo(self):
        self.solicitar(); codigo = self.enviado[0][1]
        errado = '00000000' if codigo != '00000000' else '11111111'
        for _ in range(5):
            with self.assertRaises(HTTPException): self.confirmar(errado)
        with self.assertRaises(HTTPException): self.confirmar(codigo)

    def test_limite_envios_e_codigo_antigo_invalidado(self):
        self.solicitar(); primeiro = self.enviado[0][1]
        self.solicitar(); self.solicitar(); self.solicitar()
        self.assertEqual(3,len(self.enviado))
        if primeiro != self.enviado[-1][1]:
            with self.assertRaises(HTTPException): self.confirmar(primeiro)


if __name__ == '__main__': unittest.main()
