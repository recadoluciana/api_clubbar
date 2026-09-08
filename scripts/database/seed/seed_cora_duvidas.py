from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import text

PROJECT_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_DIR))

from dotenv import load_dotenv

load_dotenv(PROJECT_DIR / ".env", override=False)

from app.database import SessionLocal


DUVIDAS = [
    (1, "Como comprar um ingresso?", "Abra o evento, escolha o ingresso e a quantidade, toque em Comprar ingressos e conclua os dados solicitados."),
    (2, "Onde encontro meus ingressos?", "Seus ingressos ficam na Carteira, acessível pela barra inferior do aplicativo."),
    (3, "Como apresentar o ingresso no evento?", "Abra a Carteira, escolha o ingresso e toque em Exibir ingresso e QR Code. Apresente o código na portaria."),
    (4, "Como cancelar a compra de um ingresso?", "Na Carteira, abra o ingresso e use a opção Cancelar. As condições de cancelamento aplicáveis serão exibidas antes da confirmação."),
    (5, "Como comprar um produto?", "Abra o estabelecimento ou o cardápio, adicione os produtos ao carrinho e finalize o pagamento."),
    (6, "Onde retiro os produtos comprados?", "Os produtos ficam disponíveis na Carteira. Apresente o ticket no estabelecimento para realizar a retirada."),
    (7, "Como alterar meus dados?", "Toque em Perfil na barra inferior e abra a opção de editar seus dados."),
    (8, "Quais formas de pagamento são aceitas?", "As formas disponíveis aparecem ao finalizar cada compra e podem variar conforme o estabelecimento e o tipo de venda."),
    (9, "Paguei e a compra não apareceu. O que faço?", "Atualize a Carteira e confira novamente após alguns instantes. Se continuar sem aparecer, envie uma mensagem para a Cora com os dados da compra."),
    (10, "Como falar com o atendimento?", "Digite sua mensagem no campo abaixo. A Cora responderá dúvidas conhecidas e registrará as demais solicitações para acompanhamento."),
]


def main() -> None:
    db = SessionLocal()
    try:
        for ordem, pergunta, resposta in DUVIDAS:
            db.execute(
                text(
                    """
                    INSERT INTO coraduvida (pergunta, resposta, idordem, sitduvida)
                    VALUES (:pergunta, :resposta, :ordem, 'ATIVA')
                    ON DUPLICATE KEY UPDATE
                        resposta = VALUES(resposta),
                        idordem = VALUES(idordem),
                        sitduvida = 'ATIVA'
                    """
                ),
                {"pergunta": pergunta, "resposta": resposta, "ordem": ordem},
            )
        db.commit()
        print(f"Dúvidas da Cora carregadas: {len(DUVIDAS)}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
