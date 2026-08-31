from app.models.usuario import Usuario
from app.services.auditoria_service import (
    AtorAuditoria,
    _criar_evento,
    _estado_completo,
    definir_ator,
    restaurar_ator,
)


def test_auditoria_preserva_snapshot_do_nome_e_email():
    usuario = Usuario(
        usuario_id=15,
        organizacao_id=3,
        nmusuario="Responsável original",
        emailuser="original@clubbar.com.br",
        senhahashuser="hash-secreto",
        dscargo="ADMIN",
        situsuario="ATIVO",
    )
    token = definir_ator(
        AtorAuditoria(
            tipo="USUARIO",
            ator_id="15",
            usuario_id=15,
            nome="Responsável original",
            email="original@clubbar.com.br",
            metodo_http="PUT",
            rota="/recurso/1",
        )
    )
    try:
        evento = _criar_evento(
            usuario,
            "ALTERACAO",
            {"nmusuario": "Nome anterior"},
            {"nmusuario": "Nome novo"},
        )
    finally:
        restaurar_ator(token)

    usuario.nmusuario = "Nome alterado posteriormente"
    usuario.emailuser = "novo@clubbar.com.br"

    assert evento.ator_nome == "Responsável original"
    assert evento.ator_email == "original@clubbar.com.br"
    assert evento.usuario_id == 15
    assert evento.operador_id is None
    assert evento.registro_id == "15"


def test_auditoria_nao_expoe_senhas_ou_tokens():
    usuario = Usuario(
        usuario_id=9,
        organizacao_id=3,
        nmusuario="Teste",
        emailuser="teste@clubbar.com.br",
        senhahashuser="hash-que-nao-pode-ser-gravado",
        dscargo="ADMIN",
        situsuario="ATIVO",
    )

    dados = _estado_completo(usuario)

    assert dados["senhahashuser"] == "<protegido>"
    assert "hash-que-nao-pode-ser-gravado" not in str(dados)
