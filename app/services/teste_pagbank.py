import requests
import json
import time

# CONFIGURAÇÕES DE TESTE
TOKEN_SANDBOX = "7b8da97f-3aaf-4fc8-80ed-79f180630ee3a2054d9341daa4402117dff6a1bd0d20d5ef-2567-41a7-bc9b-be0896a82b23"
URL_BASE = "https://sandbox.api.pagseguro.com"

def finalizar_pagamento_pix():
    # --- PASSO 1: Criar o Pedido ---
    url_orders = f"{URL_BASE}/orders"
    
    headers = {
        "Authorization": f"Bearer {TOKEN_SANDBOX}",
        "accept": "application/json"
    }

    # URL para buscar um pedido específico: /orders/{id}
    url_especifica = f"{url_orders}/{"ORDE_3F985A66-9D37-4AC1-9658-86FB1A2B4D48"}"

    print(f"Testando conexão GET para o pedido {"ORDE_3F985A66-9D37-4AC1-9658-86FB1A2B4D48"}...")

    payload_pedido = {
        "reference_id": f"PIX-TEST-{int(time.time())}",
        "customer": {
            "name": "Jose Testador",
            "email": "jose@sandbox.pagseguro.com.br",
            "tax_id": "12345678909"
        },
        "items": [
            {
                "reference_id": "ITEM01",
                "name": "Entrada ClubBar",
                "quantity": 1,
                "unit_amount": 5000 # R$ 50,00
            }
        ]
    }

    print("Enviando pedido para o Sandbox...")
    try:
        response_pedido = requests.post(url_orders, headers=headers, json=payload_pedido)
        
        if response_pedido.status_code == 201:
            data_pedido = response_pedido.json()
            order_id = data_pedido['id']
            print(f"✅ Pedido {order_id} criado com sucesso!")
        else:
            print(f"❌ Erro ao criar pedido: {response_pedido.text}")
            return

        # --- PASSO 2: Finalizar o Pagamento (PIX) ---
        url_pagar = f"{URL_BASE}/orders/{order_id}"
        
        payload_pagamento = {
            "charges": [
                {
                    "payment_method": {
                        "type": "PIX",
                        "description": "Pagamento Pix",
                        "pix": {
                            "qr_codes": [
                                {
                                    "amount": {
                                        "value": 5000
                                    }
                                }
                            ]
                        }
                    }
                }
            ]
        }
        
        print(f"Finalizando pagamento PIX em: {url_pagar}")
        
        # Usando os mesmos headers
        response_pagar = requests.post(url_pagar, headers=headers, json=payload_pagamento)
        
        if response_pagar.status_code == 200:
            print("✅ Pagamento PIX criado com sucesso!")
            # Link do QR Code estará aqui
            print(json.dumps(response_pagar.json(), indent=4))
        else:
            print(f"❌ Erro no pagamento {response_pagar.status_code}:")
            print(response_pagar.text)
            
    except Exception as e:
        print(f"⚠️ Falha na conexão: {e}")

if __name__ == "__main__":
    finalizar_pagamento_pix()