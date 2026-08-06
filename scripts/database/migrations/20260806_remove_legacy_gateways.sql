ALTER TABLE carrinho
  DROP COLUMN idpixmercadopago,
  DROP COLUMN vrpixmercadopago;

ALTER TABLE pagvenda
  ALTER COLUMN provedor SET DEFAULT 'ASAAS';
