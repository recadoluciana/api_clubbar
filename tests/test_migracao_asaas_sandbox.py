import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.routers.titularfinanceiro import migrar_vinculo_sandbox_para_producao


@pytest.mark.parametrize("ambiente", ["SANDBOX", "PRODUCAO", "INDISPONIVEL"])
def test_migracao_so_desvincula_credencial_confirmada_de_sandbox(ambiente):
    titular = SimpleNamespace(
        titularfinanceiro_id=2,
        asaas_account_id="conta-teste", asaas_wallet_id="carteira-teste",
        asaas_api_key_criptografada="credencial", status_asaas="APROVADO",
        onboarding_url=None, dtultimaverificacao=None,
    )
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = titular
    db.query.return_value.filter.return_value.all.return_value = []
    with (
        patch("app.routers.titularfinanceiro.ASAAS_BASE_URL", "https://api.asaas.com/v3"),
        patch("app.routers.titularfinanceiro.ASAAS_API_KEY", "chave-producao"),
        patch("app.routers.titularfinanceiro._validar_escopo"),
        patch("app.routers.titularfinanceiro.descriptografar_credencial", return_value="chave"),
        patch("app.routers.titularfinanceiro._identificar_ambiente_credencial_asaas", new=AsyncMock(return_value=ambiente)),
        patch("app.routers.titularfinanceiro._out", return_value={"ok": True}),
    ):
        if ambiente == "SANDBOX":
            resultado = asyncio.run(migrar_vinculo_sandbox_para_producao(1, 2, db, {}))
            assert resultado == {"ok": True}
            assert titular.asaas_account_id is None
            assert titular.asaas_wallet_id is None
            assert titular.status_asaas == "NAO_INICIADO"
            db.commit.assert_called_once()
        else:
            with pytest.raises(HTTPException):
                asyncio.run(migrar_vinculo_sandbox_para_producao(1, 2, db, {}))
            assert titular.asaas_account_id == "conta-teste"
            db.commit.assert_not_called()
