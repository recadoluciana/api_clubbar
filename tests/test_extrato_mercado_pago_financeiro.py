import unittest

from app.services.extrato_mercado_pago_service import detalhes_financeiros_pagamento


class ExtratoMercadoPagoFinanceiroTest(unittest.TestCase):
    def test_preserva_valores_reais_e_detalhes_das_taxas(self):
        resultado = detalhes_financeiros_pagamento({
            'transaction_details': {'net_received_amount': 98.27, 'total_paid_amount': 110},
            'fee_details': [
                {'type': 'mercadopago_fee', 'amount': 1.73, 'fee_payer': 'collector'},
                {'type': 'application_fee', 'amount': 10, 'fee_payer': 'collector'},
            ],
            'payment_type_id': 'credit_card', 'installments': 1,
            'money_release_date': '2026-11-18T00:00:00-03:00',
        })
        self.assertEqual(resultado['liquido_recebido'], 98.27)
        self.assertEqual(resultado['total_pago'], 110.0)
        self.assertEqual(resultado['taxas'][0], {'tipo': 'mercadopago_fee', 'valor': 1.73, 'responsavel': 'collector'})
        self.assertEqual(resultado['taxas'][1]['tipo'], 'application_fee')
        self.assertEqual(resultado['parcelas'], 1)

    def test_nao_inventa_taxas_ou_liquido_quando_nao_informados(self):
        resultado = detalhes_financeiros_pagamento({'transaction_details': {}, 'fee_details': None})
        self.assertIsNone(resultado['liquido_recebido'])
        self.assertIsNone(resultado['total_pago'])
        self.assertEqual(resultado['taxas'], [])
        self.assertIsNone(resultado['parcelas'])

    def test_zero_e_diferente_de_ausente_e_descarta_dados_invalidos(self):
        resultado = detalhes_financeiros_pagamento({
            'transaction_details': {'net_received_amount': 0, 'total_paid_amount': 'inválido'},
            'fee_details': [None, {'type': 'mercadopago_fee', 'amount': 'NaN'}, {'type': 'application_fee', 'amount': 0}],
            'installments': True,
        })
        self.assertEqual(resultado['liquido_recebido'], 0)
        self.assertIsNone(resultado['total_pago'])
        self.assertEqual(len(resultado['taxas']), 1)
        self.assertEqual(resultado['taxas'][0]['valor'], 0)
        self.assertIsNone(resultado['parcelas'])

class ConciliacaoRepasseIngressoTest(unittest.TestCase):
    def test_sinaliza_diferenca_para_revisao(self):
        from app.services.extrato_mercado_pago_service import comparar_repasse_ingresso
        pagamento = {'status': 'approved', 'money_release_status': 'released', 'transaction_amount_refunded': 0, 'transaction_details': {'net_received_amount': 99.98}}
        resultado = comparar_repasse_ingresso(pagamento, 100)
        self.assertEqual(resultado, {'valor_ingressos': 100.0, 'diferenca_repasse': -0.02})

    def test_nao_concilia_estorno_ou_pagamento_nao_liberado(self):
        from app.services.extrato_mercado_pago_service import comparar_repasse_ingresso
        base = {'status': 'approved', 'money_release_status': 'released', 'transaction_amount_refunded': 1, 'transaction_details': {'net_received_amount': 99}}
        self.assertIsNone(comparar_repasse_ingresso(base, 100)['diferenca_repasse'])
        base['transaction_amount_refunded'] = 0
        base['money_release_status'] = 'pending'
        self.assertIsNone(comparar_repasse_ingresso(base, 100)['diferenca_repasse'])
        base['money_release_status'] = 'released'
        del base['transaction_amount_refunded']
        self.assertIsNone(comparar_repasse_ingresso(base, 100)['diferenca_repasse'])

class DetalheAntecipacaoTest(unittest.TestCase):
    def test_acrescenta_antecipacao_sem_duplicar_tarifas_ja_informadas(self):
        pagamento = {
            'fee_details': [
                {'type': 'mercadopago_fee', 'amount': 0.14, 'fee_payer': 'collector'},
                {'type': 'application_fee', 'amount': 2.76, 'fee_payer': 'collector'},
            ],
            'charges_details': [
                {'type': 'fee', 'name': 'mercadopago_fee', 'accounts': {'from': 'collector'}, 'amounts': {'original': 0.14, 'refunded': 0}},
                {'type': 'fee', 'name': 'third_payment', 'accounts': {'from': 'collector'}, 'amounts': {'original': 2.76, 'refunded': 0}},
                {'type': 'fee', 'name': 'financed_advance_fee', 'accounts': {'from': 'collector'}, 'amounts': {'original': 0.14, 'refunded': 0}},
            ],
        }
        taxas = detalhes_financeiros_pagamento(pagamento)['taxas']
        self.assertEqual([t['tipo'] for t in taxas], ['mercadopago_fee', 'application_fee', 'financed_advance_fee'])
        self.assertEqual(taxas[2]['valor'], 0.14)
        self.assertEqual(taxas[2]['responsavel'], 'collector')
        self.assertAlmostEqual(sum(t['valor'] for t in taxas), 3.04)

    def test_nao_duplicar_antecipacao_nem_inferir_estorno(self):
        pagamento = {
            'fee_details': [{'type': 'financed_advance_fee', 'amount': 0.14}],
            'charges_details': [{'type': 'fee', 'name': 'financed_advance_fee', 'amounts': {'original': 0.14, 'refunded': 0}}],
        }
        self.assertEqual(len(detalhes_financeiros_pagamento(pagamento)['taxas']), 1)
        pagamento['fee_details'] = []
        pagamento['charges_details'][0]['amounts']['refunded'] = 0.05
        self.assertEqual(detalhes_financeiros_pagamento(pagamento)['taxas'], [])
