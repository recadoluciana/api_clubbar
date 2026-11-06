from fastapi import HTTPException


def tratar_integridade_documento(db, erro):
    db.rollback()
    detalhe = str(getattr(erro, "orig", erro)).lower()
    if "uk_leadestabelecimento_cpfcnpj" in detalhe or "leadestabelecimento.cpfcnpj" in detalhe:
        raise HTTPException(409, "CPF ou CNPJ já cadastrado em outro estabelecimento.") from erro
    raise erro
