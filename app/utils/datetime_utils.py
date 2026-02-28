from datetime import datetime


def formatar_data_br(dt):
    """
    Aceita datetime ou string ISO
    Retorna string no formato BR: dd/mm/yyyy HH:MM
    """
    if not dt:
        return ""

    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", ""))
        except Exception:
            return dt

    return dt.strftime("%d/%m/%Y %H:%M")