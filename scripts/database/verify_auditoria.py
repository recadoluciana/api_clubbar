"""Executa uma inclusão e exclusão descartáveis para validar a auditoria."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_DIR))

import main  # noqa: F401 - registra os eventos globais de auditoria
from app.database import SessionLocal
from app.models.auditoria import Auditoria
from app.models.operador import Operador
from app.models.pais import Pais
from app.services.auditoria_service import AtorAuditoria, definir_ator, restaurar_ator


CODIGO_TESTE = 999999999


def main_verificacao() -> None:
    with SessionLocal() as db:
        operador = db.query(Operador).order_by(Operador.operador_id).first()
        if operador is None:
            raise RuntimeError("Crie o operador administrativo antes da verificação")

        anterior = db.query(Pais).filter(Pais.cdpais == CODIGO_TESTE).first()
        if anterior is not None:
            db.delete(anterior)
            db.commit()

        token = definir_ator(
            AtorAuditoria(
                tipo="OPERADOR",
                ator_id=str(operador.operador_id),
                operador_id=operador.operador_id,
                nome=operador.nmoperador,
                email=operador.emailoperador,
                metodo_http="TEST",
                rota="/verificacao-auditoria",
            )
        )
        try:
            pais = Pais(cdpais=CODIGO_TESTE, nmpais="Teste de auditoria", sgpais="TA")
            db.add(pais)
            db.commit()
            pais_id = pais.pais_id

            db.delete(pais)
            db.commit()
        finally:
            restaurar_ator(token)

        eventos = (
            db.query(Auditoria)
            .filter(
                Auditoria.tabela == "pais",
                Auditoria.registro_id == str(pais_id),
                Auditoria.rota == "/verificacao-auditoria",
            )
            .order_by(Auditoria.auditoria_id)
            .all()
        )
        acoes = [evento.acao for evento in eventos]
        if acoes != ["INCLUSAO", "EXCLUSAO"]:
            raise RuntimeError(f"Eventos inesperados: {acoes}")
        if any(evento.ator_nome != operador.nmoperador for evento in eventos):
            raise RuntimeError("O snapshot do nome do operador não foi preservado")

        print(
            "Auditoria validada: INCLUSAO e EXCLUSAO registradas para "
            f"o operador {operador.nmoperador}."
        )


if __name__ == "__main__":
    main_verificacao()
