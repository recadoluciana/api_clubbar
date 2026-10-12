ALTER TABLE loja ADD COLUMN permiteentrega CHAR(1) NOT NULL DEFAULT 'N' AFTER vendaingressos;
ALTER TABLE checkout_asaas ADD COLUMN dadosentrega TEXT NULL AFTER asaas_wallet_clubbar;
