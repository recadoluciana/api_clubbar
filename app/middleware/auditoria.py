import hashlib

from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import JWT_SECRET
from app.database import SessionLocal
from app.models.cliente import Cliente
from app.models.leadacesso import LeadAcesso
from app.models.leadparceiro import LeadParceiro
from app.models.operador import Operador
from app.models.usuario import Usuario
from app.services.auditoria_service import AtorAuditoria, definir_ator, restaurar_ator


class AuditoriaMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        ator = _resolver_ator(request)
        token_contexto = definir_ator(ator)
        try:
            return await call_next(request)
        finally:
            restaurar_ator(token_contexto)


def _resolver_ator(request) -> AtorAuditoria:
    metodo = request.method.upper()
    rota = request.url.path
    padrao = AtorAuditoria(metodo_http=metodo, rota=rota)
    cabecalho = request.headers.get("authorization", "")
    if not cabecalho.lower().startswith("bearer "):
        return padrao

    token = cabecalho.split(" ", 1)[1].strip()
    if not token:
        return padrao

    db = SessionLocal()
    try:
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        except JWTError:
            payload = None

        if payload:
            identificador = int(payload["sub"])
            papel = (payload.get("role") or payload.get("tipo") or "").lower()
            if papel == "operador":
                item = db.get(Operador, identificador)
                if item:
                    return AtorAuditoria(
                        tipo="OPERADOR", ator_id=str(identificador),
                        operador_id=identificador, nome=item.nmoperador,
                        email=item.emailoperador, metodo_http=metodo, rota=rota,
                    )
            elif papel == "cliente":
                item = db.get(Cliente, identificador)
                if item:
                    return AtorAuditoria(
                        tipo="CLIENTE", ator_id=str(identificador),
                        nome=item.nmcliente, email=item.emailcliente,
                        metodo_http=metodo, rota=rota,
                    )
            else:
                item = db.get(Usuario, identificador)
                if item:
                    return AtorAuditoria(
                        tipo="USUARIO", ator_id=str(identificador),
                        usuario_id=identificador, nome=item.nmusuario,
                        email=item.emailuser, metodo_http=metodo, rota=rota,
                    )

        tokenhash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        resultado = (
            db.query(LeadParceiro)
            .join(LeadAcesso, LeadAcesso.leadparceiro_id == LeadParceiro.leadparceiro_id)
            .filter(LeadAcesso.tokenhash == tokenhash, LeadAcesso.revogado == "N")
            .first()
        )
        if resultado:
            return AtorAuditoria(
                tipo="LEAD", ator_id=str(resultado.leadparceiro_id),
                nome=resultado.nmresponsavel, email=resultado.email,
                metodo_http=metodo, rota=rota,
            )
    except (KeyError, TypeError, ValueError):
        return padrao
    finally:
        db.close()
    return padrao
