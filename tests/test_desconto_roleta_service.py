from decimal import Decimal

import pytest

from app.services.desconto_roleta_service import melhor_preco_roleta


@pytest.mark.parametrize("base,atual,percentual,esperado,aplicado", [
    (10, 10, 20, "8.00", True),
    (10, 7, 20, "7.00", False),
    (27, 24, 20, "21.60", True),
    (27, 20, 20, "20.00", False),
    (10, 8, 20, "8.00", False),
])
def test_compara_melhor_promocao_sem_acumulacao(base, atual, percentual, esperado, aplicado):
    assert melhor_preco_roleta(base, atual, percentual) == (Decimal(esperado), aplicado)


@pytest.mark.parametrize("base,atual,percentual", [(-1, 1, 20), (1, -1, 20), (1, 1, 101)])
def test_rejeita_valores_invalidos(base, atual, percentual):
    with pytest.raises(ValueError):
        melhor_preco_roleta(base, atual, percentual)


def test_desconto_zero_nao_altera_preco():
    assert melhor_preco_roleta(10, 10, 0) == (Decimal("10.00"), False)


def test_dez_por_cento_e_arredondado_em_centavos():
    assert melhor_preco_roleta("19.90", "19.90", 10) == (Decimal("17.91"), True)
def test_indice_preserva_giros_antigos_e_limita_giro_de_carrinho():
    import sqlite3

    db = sqlite3.connect(':memory:')
    db.execute('CREATE TABLE premios (carrinho_id INTEGER, produto_id INTEGER, origem_giro TEXT)')
    db.execute('CREATE UNIQUE INDEX uk ON premios (carrinho_id, produto_id, origem_giro)')
    db.executemany('INSERT INTO premios VALUES (?, ?, ?)', [(5, 3, None), (5, 3, None)])
    db.execute('INSERT INTO premios VALUES (?, ?, ?)', (5, 3, 'CARRINHO'))
    try:
        db.execute('INSERT INTO premios VALUES (?, ?, ?)', (5, 3, 'CARRINHO'))
        assert False, 'Um segundo giro de carrinho não deve criar outro registro'
    except sqlite3.IntegrityError:
        pass

