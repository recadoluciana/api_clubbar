import unittest

from app.models.itvenda import ItVenda
from app.models.reserva_ingresso import ReservaIngresso
from app.models.venda import Venda


class ModeloVendaTest(unittest.TestCase):
    def test_item_de_venda_aceita_produto_ou_lote(self):
        self.assertTrue(ItVenda.__table__.c.produto_id.nullable)
        self.assertTrue(ItVenda.__table__.c.lote_id.nullable)
        self.assertFalse(ItVenda.__table__.c.tipoitem.nullable)
        self.assertEqual(
            set(ItVenda.__table__.c.tipoitem.type.enums),
            {"PRODUTO", "INGRESSO"},
        )

    def test_venda_tem_tipo_explicito(self):
        self.assertFalse(Venda.__table__.c.tipovenda.nullable)
        self.assertEqual(
            set(Venda.__table__.c.tipovenda.type.enums),
            {"PRODUTO", "INGRESSO"},
        )

    def test_reserva_nao_depende_de_produto_espelho(self):
        self.assertNotIn("produto_id", ReservaIngresso.__table__.c)


if __name__ == "__main__":
    unittest.main()
