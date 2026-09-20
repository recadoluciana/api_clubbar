# app/routers/localidades.py
import httpx

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.cidade import Cidade
from app.models.estado import Estado

router = APIRouter(prefix="/localidades", tags=["Localidades"])


@router.get("/cep/{cep}")
def consultar_cep(cep: str, db: Session = Depends(get_db)):
    cep_limpo = "".join(caractere for caractere in cep if caractere.isdigit())
    if len(cep_limpo) != 8:
        raise HTTPException(status_code=422, detail="Informe um CEP válido com 8 dígitos.")
    try:
        resposta = httpx.get(
            f"https://viacep.com.br/ws/{cep_limpo}/json/",
            timeout=5,
        )
        resposta.raise_for_status()
        dados = resposta.json()
    except (httpx.HTTPError, ValueError) as erro:
        raise HTTPException(
            status_code=503,
            detail="Não foi possível consultar o CEP agora. Tente novamente.",
        ) from erro
    if dados.get("erro") or not dados.get("cep"):
        raise HTTPException(status_code=404, detail="CEP não encontrado.")

    estado = (
        db.query(Estado)
        .filter(Estado.sgestado == str(dados.get("uf") or "").upper())
        .first()
    )
    cidade = None
    ibge = str(dados.get("ibge") or "").strip()
    if estado and ibge.isdigit():
        cidade = (
            db.query(Cidade)
            .filter(
                Cidade.estado_id == estado.estado_id,
                Cidade.cdibgecid == int(ibge),
            )
            .first()
        )
    if estado is None or cidade is None:
        raise HTTPException(
            status_code=422,
            detail="O estado ou a cidade deste CEP não está cadastrado no sistema.",
        )
    return {
        "cep": cep_limpo,
        "endereco": dados.get("logradouro") or "",
        "bairro": dados.get("bairro") or "",
        "estado_id": estado.estado_id,
        "sgestado": estado.sgestado,
        "cidade_id": cidade.cidade_id,
        "nmcidade": cidade.nmcidade,
    }

@router.get("/estados")
def listar_estados(db: Session = Depends(get_db)):
    estados = db.query(Estado).order_by(Estado.nmestado.asc()).all()
    return [
        {
            "estado_id": estado.estado_id,
            "cdibgeest": estado.cdibgeest,
            "sgestado": estado.sgestado,
            "nmestado": estado.nmestado,
            "pais_id": estado.pais_id,
        }
        for estado in estados
    ]

@router.get("/estados/{estado_id}/cidades")
def listar_cidades_por_estado(estado_id: int, db: Session = Depends(get_db)):
    estado = db.query(Estado).filter(Estado.estado_id == estado_id).first()
    if not estado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Estado não encontrado.",
        )

    cidades = (
        db.query(Cidade, Estado)
        .join(
            Estado,
            Estado.estado_id == Cidade.estado_id,
        )
        .filter(
            Cidade.estado_id == estado_id,
        )
        .order_by(
            Cidade.nmcidade.asc(),
        )
        .all()
    )

    return [
        {
            "cidade_id": cidade.cidade_id,
            "cdibgecid": cidade.cdibgecid,
            "estado_id": cidade.estado_id,
            "nmcidade": cidade.nmcidade,
            "sgestado": estado.sgestado,
            "label": f"{cidade.nmcidade} - {estado.sgestado}",
            "pais_id": cidade.pais_id,
        }
        for cidade, estado in cidades
    ]
