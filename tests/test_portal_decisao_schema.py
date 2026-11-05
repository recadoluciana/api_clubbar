import unittest

from pydantic import ValidationError

from app.schemas.portalparceiro import PortalEstabelecimentoCreate, PortalStatusUpdate
from app.schemas.leadparceiro import ConverterLeadParceiroIn


class PortalStatusSchemaTest(unittest.TestCase):
    def test_novos_tipos_e_venda_padrao(self):
        for tipo in ('RESTAURANTE', 'CONVENIENCIA'):
            cadastro = PortalEstabelecimentoCreate(
                nmestabelecimento='Exemplo', tipo=tipo, estado_id=1, cidade_id=1,
                cep='37185000', endereco='Rua A', numero='1', bairro='Centro',
            )
            self.assertEqual(cadastro.tipovenda, 'AMBOS')
            self.assertIsNone(cadastro.nmresponsavel)
            self.assertEqual(
                ConverterLeadParceiroIn(tipo_loja=tipo, email_responsavel='pessoa@example.com').tipo_loja,
                tipo,
            )

    def test_permite_status_de_decisao(self):
        for status in ("NEGOCIANDO", "ACEITOU_PARCERIA", "RECUSOU_PARCERIA"):
            self.assertEqual(status, PortalStatusUpdate(status=status).status)

    def test_portal_nao_pode_converter_diretamente(self):
        with self.assertRaises(ValidationError):
            PortalStatusUpdate(status="CONVERTIDO")


if __name__ == "__main__":
    unittest.main()
