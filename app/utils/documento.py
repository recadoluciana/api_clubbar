import re


def normalizar_cpf_cnpj(valor: str | None) -> str | None:
    """Normaliza CPF/CNPJ sem descartar letras dos novos CNPJs."""
    if valor is None:
        return None
    documento = re.sub(r"[^0-9A-Za-z]", "", valor).upper()
    if not documento:
        return None
    if len(documento) == 11 and documento.isdigit():
        return documento
    if len(documento) == 14 and documento[:12].isalnum() and documento[-2:].isdigit():
        return documento
    raise ValueError("Informe um CPF com 11 dígitos ou um CNPJ válido com 14 posições.")


def raiz_cnpj(valor: str | None) -> str | None:
    documento = normalizar_cpf_cnpj(valor)
    return documento[:8] if documento and len(documento) == 14 else None


def tipo_estabelecimento_inferido(valor: str | None) -> str | None:
    """Infere somente o padrão legado seguro; novos CNPJs podem ser informados manualmente."""
    documento = normalizar_cpf_cnpj(valor)
    if not documento or len(documento) != 14:
        return None
    ordem = documento[8:12]
    if ordem == "0001":
        return "MATRIZ"
    if ordem.isdigit():
        return "FILIAL"
    return None


def validar_cpf_responsavel(valor: str) -> str:
    """Normaliza e valida os dígitos verificadores do CPF de uma pessoa."""
    if not isinstance(valor, str) or not re.fullmatch(r"[0-9.\-\s]+", valor):
        raise ValueError("Informe um CPF válido.")
    cpf = re.sub(r"[.\-\s]", "", valor)
    if len(cpf) != 11 or len(set(cpf)) == 1:
        raise ValueError("Informe um CPF válido.")
    for tamanho in (9, 10):
        soma = sum(int(numero) * (tamanho + 1 - indice) for indice, numero in enumerate(cpf[:tamanho]))
        digito = (soma * 10 % 11) % 10
        if digito != int(cpf[tamanho]):
            raise ValueError("Informe um CPF válido.")
    return cpf
