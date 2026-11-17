import asyncio
import csv
import io
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from app.core.security import criar_jwt
from app.routers import relatorio_split_mercado_pago as relatorio


class QueryFake:
    def join(self, *args): return self
    def filter(self, *args): return self
    def all(self): return [('111',)]


class RelatorioSplitTest(unittest.TestCase):
    def setUp(self):
        self.usuario = {'role': 'usuario', 'dscargo': 'ADMIN', 'organizacao_id': 42}
        self.comprovante = criar_jwt({'tipo': 'relatorio_split', 'organizacao_id': 42, 'relatorio_id': '321'})

    def test_comprovante_de_outra_empresa_e_recusado(self):
        with self.assertRaises(HTTPException) as erro:
            relatorio._report_id(self.comprovante, 43)
        self.assertEqual(erro.exception.status_code, 403)

    def test_admin_e_necessario(self):
        with self.assertRaises(HTTPException):
            asyncio.run(relatorio.gerar(relatorio.Periodo(inicio=date(2026, 1, 1), fim=date(2026, 1, 2)), {'role': 'usuario', 'dscargo': 'OPERADOR', 'organizacao_id': 42}))

    def test_brasilia_periodo_e_gerado_em_utc(self):
        resposta = SimpleNamespace(json=lambda: {'request_id': 321})
        with patch.object(relatorio, '_config', return_value=('token', 1, 2)), patch.object(relatorio, '_request', new_callable=AsyncMock, return_value=resposta) as request:
            asyncio.run(relatorio.gerar(relatorio.Periodo(inicio=date(2026, 1, 1), fim=date(2026, 1, 2)), self.usuario))
        datas = request.call_args.kwargs['json']['origin']['data']
        self.assertEqual(datas['date_start'], '2026-01-01T03:00:00Z')
        self.assertEqual(datas['date_end'], '2026-01-03T02:59:59.999000Z')

    def test_somente_pagamentos_autorizados_sao_exibidos(self):
        saida = io.StringIO()
        writer = csv.DictWriter(saida, fieldnames=relatorio.CAMPOS, delimiter=';')
        writer.writeheader()
        writer.writerow({'PAYMENT': '111', 'COLLECTOR': '10', 'TRANSACTION_AMOUNT': '110'})
        writer.writerow({'PAYMENT': '222', 'COLLECTOR': '20', 'TRANSACTION_AMOUNT': '999'})
        respostas = [SimpleNamespace(json=lambda: {'status': 'available'}), SimpleNamespace(content=saida.getvalue().encode())]
        with patch.object(relatorio, '_config', return_value=('token', 1, 2)), patch.object(relatorio, '_request', new_callable=AsyncMock, side_effect=respostas):
            resultado = asyncio.run(relatorio.consultar({'comprovante': self.comprovante}, self.usuario, SimpleNamespace(query=lambda *args: QueryFake())))
        self.assertEqual([item['PAYMENT'] for item in resultado['itens']], ['111'])

    def test_estrutura_incompleta_nao_e_aceita(self):
        respostas = [SimpleNamespace(json=lambda: {'status': 'available'}), SimpleNamespace(content=b'PAYMENT;COLLECTOR\n111;10')]
        with patch.object(relatorio, '_config', return_value=('token', 1, 2)), patch.object(relatorio, '_request', new_callable=AsyncMock, side_effect=respostas):
            with self.assertRaises(HTTPException) as erro:
                asyncio.run(relatorio.consultar({'comprovante': self.comprovante}, self.usuario, SimpleNamespace()))
        self.assertEqual(erro.exception.status_code, 502)
