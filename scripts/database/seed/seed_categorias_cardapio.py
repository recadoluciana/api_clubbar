from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text

PROJECT_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_DIR))
load_dotenv(PROJECT_DIR / ".env", override=False)

from app.database import SessionLocal


# Nomes semânticos de Material Icons; cada interface faz o mapeamento visual.
CATEGORIAS = [
    ("Águas", "water_drop"), ("Refrigerantes", "local_drink"),
    ("Sucos", "local_cafe"), ("Energéticos", "bolt"),
    ("Isotônicos", "sports_bar"), ("Água de coco", "emoji_nature"),
    ("Bebidas sem álcool", "no_drinks"), ("Cervejas", "sports_bar"),
    ("Cervejas artesanais", "sports_bar"), ("Chopes", "sports_bar"),
    ("Drinks", "local_bar"), ("Coquetéis sem álcool", "local_bar"),
    ("Caipirinhas", "local_bar"), ("Doses", "liquor"),
    ("Destilados", "liquor"), ("Cachaças", "liquor"),
    ("Whiskies", "liquor"), ("Vodcas", "liquor"),
    ("Gins", "liquor"), ("Tequilas", "liquor"),
    ("Licores", "liquor"), ("Vinhos", "wine_bar"),
    ("Espumantes", "wine_bar"), ("Combos de bebidas", "inventory_2"),
    ("Baldes de cerveja", "icecream"), ("Garrafas", "liquor"),
    ("Cafés", "coffee"), ("Chás", "emoji_food_beverage"),
    ("Caldos", "soup_kitchen"), ("Sopas", "soup_kitchen"),
    ("Porções", "tapas"), ("Petiscos", "tapas"),
    ("Entradas", "restaurant"), ("Tábuas e frios", "lunch_dining"),
    ("Frituras", "skillet"), ("Espetinhos", "kebab_dining"),
    ("Churrasco", "outdoor_grill"), ("Lanches", "lunch_dining"),
    ("Hambúrgueres", "lunch_dining"), ("Hot dogs", "fastfood"),
    ("Sanduíches", "lunch_dining"), ("Pizzas", "local_pizza"),
    ("Massas", "dinner_dining"), ("Saladas", "eco"),
    ("Refeições", "restaurant"), ("Pratos executivos", "room_service"),
    ("Pratos individuais", "dinner_dining"),
    ("Pratos para compartilhar", "groups"),
    ("Pratos infantis", "child_care"),
    ("Comida brasileira", "restaurant_menu"),
    ("Comida mineira", "restaurant_menu"),
    ("Comida japonesa", "set_meal"),
    ("Comida mexicana", "dinner_dining"),
    ("Comida italiana", "dinner_dining"),
    ("Frutos do mar", "set_meal"), ("Vegetarianos", "eco"),
    ("Veganos", "grass"), ("Sobremesas", "cake"),
    ("Doces", "cookie"), ("Sorvetes", "icecream"),
    ("Açaí", "icecream"), ("Combos", "inventory_2"),
    ("Promoções", "sell"), ("Happy hour", "celebration"),
    ("Camarotes", "event_seat"),
    ("Mesas e reservas", "table_restaurant"),
    ("Pacotes para eventos", "event"),
    ("Kits para festas", "celebration"),
    ("Produtos do evento", "festival"),
    ("Merchandising", "checkroom"), ("Souvenires", "redeem"),
    ("Outros", "more_horiz"),
]


def main() -> None:
    db = SessionLocal()
    try:
        for ordem, (nome, icone) in enumerate(CATEGORIAS, start=1):
            db.execute(
                text(
                    """
                    INSERT INTO categoriapadrao
                        (nmcategoria, dsicone, sitcategoria, idordcategoria)
                    VALUES (:nome, :icone, 'ATIVA', :ordem)
                    ON DUPLICATE KEY UPDATE
                        dsicone = VALUES(dsicone),
                        sitcategoria = 'ATIVA',
                        idordcategoria = VALUES(idordcategoria)
                    """
                ),
                {"nome": nome, "icone": icone, "ordem": ordem},
            )
        db.commit()
        print(f"Categorias padrão carregadas: {len(CATEGORIAS)}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
