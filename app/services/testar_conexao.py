import requests

# CONFIGURAÇÕES DE TESTE
TOKEN_SANDBOX = "7b8da97f-3aaf-4fc8-80ed-79f180630ee3a2054d9341daa4402117dff6a1bd0d20d5ef-2567-41a7-bc9b-be0896a82b23"
URL_SANDBOX_BASE = "https://sandbox.api.pagseguro.com/orders"

# --- COLE UM ID DE PEDIDO QUE VOCÊ GEROU ANTES ---
ORDER_ID = "ORDE_C4DCE533-2841-45A7-87D4-10AF0B0A0472" 

def testar_conexao():
    headers = {
        "Authorization": f"Bearer {TOKEN_SANDBOX}",
        "accept": "application/json"
    }

    # URL para buscar um pedido específico: /orders/{id}
    url_especifica = f"{URL_SANDBOX_BASE}/{"ORDE_3F985A66-9D37-4AC1-9658-86FB1A2B4D48"}"

    print(f"Testando conexão GET para o pedido {"ORDE_3F985A66-9D37-4AC1-9658-86FB1A2B4D48"}...")
    try:
        response = requests.get(url_especifica, headers=headers)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Conexão validada! Pedido encontrado.")
        elif response.status_code == 404:
            print("❌ Pedido não encontrado (404), mas a API respondeu.")
        else:
            print(f"❌ Erro na conexão: {response.text}")
            
    except Exception as e:
        print(f"Erro de rede: {e}")

if __name__ == "__main__":
    testar_conexao()