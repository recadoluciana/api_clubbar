-- Registra o envio da confirmação ao cliente sem misturar pagamento e e-mail.
-- A aplicação também executa esta alteração de forma idempotente no startup.
ALTER TABLE checkout_mercadopago
    ADD COLUMN dtemailconfirmacao DATETIME NULL AFTER dtconfirmacao;
