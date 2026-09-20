import unittest
from unittest.mock import patch

from app.services.public_urls import (
    url_logo_email,
    url_partner_publico,
    url_site_publico,
)


class PublicUrlsTest(unittest.TestCase):
    @patch.dict("os.environ", {"APP_ENV": "development"}, clear=False)
    def test_urls_de_desenvolvimento(self):
        self.assertEqual(
            "https://clubbarsite-desenvolvimento.up.railway.app",
            url_site_publico(),
        )
        self.assertEqual(
            "https://clubbarpartner-desenvolvimento.up.railway.app",
            url_partner_publico(),
        )
        self.assertEqual(
            "https://clubbarsite-desenvolvimento.up.railway.app/assets/images/logo.png",
            url_logo_email(),
        )

    @patch.dict("os.environ", {"APP_ENV": "production"}, clear=False)
    def test_urls_de_producao(self):
        self.assertEqual("https://clubbar.com.br", url_site_publico())
        self.assertEqual("https://partner.clubbar.com.br", url_partner_publico())
        self.assertEqual(
            "https://clubbar.com.br/assets/images/logo.png",
            url_logo_email(),
        )
