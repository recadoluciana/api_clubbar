from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo


FUSO_BRASIL = ZoneInfo("America/Sao_Paulo")


def inicio_dia_brasil_em_utc(data: date) -> datetime:
    """Início do dia civil em Brasília, em UTC sem fuso como no banco."""
    return datetime.combine(data, time.min, tzinfo=FUSO_BRASIL).astimezone(
        timezone.utc
    ).replace(tzinfo=None)


def para_fuso_br(dt):
    if not dt:
        return dt
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except Exception:
            return dt
    # Datas do banco são armazenadas como horário civil de Brasília sem tzinfo.
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=FUSO_BRASIL)
    return dt.astimezone(FUSO_BRASIL)


def iso_utc(dt):
    """Serializa horário persistido como horário de Brasília.

    O nome é mantido por compatibilidade com os chamadores existentes.
    A API agora expõe o offset de Brasília para que as telas não precisem
    interpretar um horário civil como UTC.
    """
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=FUSO_BRASIL)
    return dt.astimezone(FUSO_BRASIL).isoformat()


def iso_utc_de_horario_brasil(dt):
    """Serializa horários civis persistidos em Brasília com o offset local."""
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=FUSO_BRASIL)
    return dt.astimezone(FUSO_BRASIL).isoformat()


def formatar_data_br(dt):
    """
    Aceita datetime ou string ISO
    Retorna string no formato BR: dd/mm/yyyy HH:MM
    """
    if not dt:
        return ""

    convertido = para_fuso_br(dt)
    return convertido.strftime("%d/%m/%Y %H:%M") if isinstance(convertido, datetime) else convertido
