import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from app.models.itvenda import ItVenda
from app.models.pagvenda import PagVenda
from app.models.usuario import Usuario
from app.routers.entregas import entregar_produto_por_token


class ConfirmarEntregaPagamentoTest(unittest.TestCase):
    def confirmar(self, pagamento, venda):
        usuario = SimpleNamespace(usuario_id=7, loja_id=1, dscargo='MOTOBOY', nmusuario='Entregador')
        pedido = SimpleNamespace(pedidoentrega_id=9, situacaopedido='EM_ROTA')
        db = MagicMock()
        query_usuario = MagicMock()
        query_usuario.filter.return_value.first.return_value = usuario
        query_pagamento = MagicMock()
        query_pagamento.filter.return_value.order_by.return_value.with_for_update.return_value.first.return_value = pagamento
        query_itens = MagicMock()
        db.query.side_effect = lambda model: {
            Usuario: query_usuario, PagVenda: query_pagamento, ItVenda: query_itens,
        }[model]
        with patch('app.routers.entregas._pedido_entrega_por_token', return_value=(pedido, venda, object(), object())), \
             patch('app.routers.entregas._resumo_pedido_entrega', return_value={}):
            resultado = entregar_produto_por_token('token', 7, payload={'sub': '7'}, db=db)
        return resultado, pedido, db, query_itens

    def test_pagamento_por_gateway_preserva_transacao_e_data(self):
        horario = datetime(2026, 11, 4, 19, 10)
        pagamento = SimpleNamespace(sitpagvenda='PAGO', dsmetodopag='PIX', provedor='MERCADO_PAGO',
                                    idtransacaopagvenda='mp-123', dtconftranspagvenda=horario)
        venda = SimpleNamespace(venda_id=3, loja_id=1, sitvenda='PAGA')
        resultado, pedido, db, _ = self.confirmar(pagamento, venda)
        self.assertEqual(pedido.situacaopedido, 'ENTREGUE')
        self.assertEqual(pagamento.idtransacaopagvenda, 'mp-123')
        self.assertEqual(pagamento.dtconftranspagvenda, horario)
        self.assertEqual(resultado['msg'], 'Entrega confirmada.')
        db.commit.assert_called_once()

    def test_pagamento_na_entrega_e_registrado(self):
        pagamento = SimpleNamespace(sitpagvenda='PENDENTE', dsmetodopag='PAGAMENTO_ENTREGA',
                                    provedor='ENTREGA', idtransacaopagvenda=None, dtconftranspagvenda=None)
        venda = SimpleNamespace(venda_id=3, loja_id=1, sitvenda='PENDENTE')
        _, pedido, _, _ = self.confirmar(pagamento, venda)
        self.assertEqual(pedido.situacaopedido, 'ENTREGUE')
        self.assertEqual(pagamento.sitpagvenda, 'PAGO')
        self.assertEqual(pagamento.idtransacaopagvenda, 'ENTREGA-9')
        self.assertEqual(venda.sitvenda, 'PAGA')

    def test_pagamento_eletronico_pendente_nao_dara_baixa(self):
        pagamento = SimpleNamespace(sitpagvenda='PENDENTE', dsmetodopag='PIX', provedor='ASAAS')
        venda = SimpleNamespace(venda_id=3, loja_id=1, sitvenda='PENDENTE')
        with self.assertRaises(HTTPException) as erro:
            self.confirmar(pagamento, venda)
        self.assertEqual(erro.exception.status_code, 409)
        self.assertEqual(pagamento.sitpagvenda, 'PENDENTE')
        self.assertEqual(venda.sitvenda, 'PENDENTE')


if __name__ == '__main__':
    unittest.main()
