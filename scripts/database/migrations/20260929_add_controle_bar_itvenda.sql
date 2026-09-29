-- Controle de produção e entrega do bar, separado da baixa legada de retirada.
-- MySQL atual aceita IF NOT EXISTS, tornando a aplicação repetível nos dois ambientes.
ALTER TABLE itvenda
  ADD COLUMN IF NOT EXISTS idcontrolebar ENUM('PENDENTE', 'EM_PRODUCAO', 'ENTREGUE')
  NOT NULL DEFAULT 'PENDENTE' AFTER dtentregaitvenda;

ALTER TABLE itvenda
  ADD COLUMN IF NOT EXISTS nrmesa VARCHAR(50) NULL AFTER idcontrolebar;
