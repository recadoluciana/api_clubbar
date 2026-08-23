from datetime import datetime, timezone
from zoneinfo import ZoneInfo


FUSO_BRASIL = ZoneInfo("America/Sao_Paulo")


def para_fuso_br(dt):
    if not dt:
        return dt
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except Exception:
            return dt
    # Datas automáticas do banco são armazenadas em UTC sem tzinfo pelo MySQL.
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(FUSO_BRASIL)


def iso_utc(dt):
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def formatar_data_br(dt):
    """
    Aceita datetime ou string ISO
    Retorna string no formato BR: dd/mm/yyyy HH:MM
    """
    if not dt:
        return ""

    convertido = para_fuso_br(dt)
    return convertido.strftime("%d/%m/%Y %H:%M") if isinstance(convertido, datetime) else convertido
