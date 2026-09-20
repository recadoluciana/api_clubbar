import os


_AMBIENTES_DESENVOLVIMENTO = {"dev", "development"}


def ambiente_desenvolvimento() -> bool:
    ambiente = os.getenv("APP_ENV", "development").strip().lower()
    return ambiente in _AMBIENTES_DESENVOLVIMENTO


def url_site_publico() -> str:
    if ambiente_desenvolvimento():
        return "https://clubbarsite-desenvolvimento.up.railway.app"
    return "https://clubbar.com.br"


def url_partner_publico() -> str:
    if ambiente_desenvolvimento():
        return "https://clubbarpartner-desenvolvimento.up.railway.app"
    return "https://partner.clubbar.com.br"


def url_logo_email() -> str:
    return f"{url_site_publico()}/assets/images/logo.png"
