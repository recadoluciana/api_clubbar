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


def validar_documento_acesso(valor: str) -> str:
    """Valida os DVs de CPF ou CNPJ numérico/alfanumérico de acesso."""
    if not isinstance(valor, str) or not re.fullmatch(r"[A-Za-z0-9./\-\s]+", valor):
        raise ValueError("Informe um CPF ou CNPJ válido.")
    documento = re.sub(r"[./\-\s]", "", valor).upper()
    if len(documento) == 11:
        return validar_cpf_responsavel(documento)
    if not re.fullmatch(r"[A-Z0-9]{12}[0-9]{2}", documento):
        raise ValueError("Informe um CPF ou CNPJ válido.")
    if documento.isdigit() and len(set(documento)) == 1:
        raise ValueError("Informe um CPF ou CNPJ válido.")
    for tamanho, pesos in ((12, (5,4,3,2,9,8,7,6,5,4,3,2)), (13, (6,5,4,3,2,9,8,7,6,5,4,3,2))):
        soma = sum((ord(caractere) - 48) * peso for caractere, peso in zip(documento[:tamanho], pesos))
        resto = soma % 11
        if int(documento[tamanho]) != (0 if resto < 2 else 11 - resto):
            raise ValueError("Informe um CPF ou CNPJ válido.")
    return documento
