-- Controle de produção e entrega do bar, separado da baixa legada de retirada.
-- Esta migration deve ser executada uma vez em cada ambiente.
ALTER TABLE itvenda
  ADD COLUMN idcontrolebar ENUM('PENDENTE', 'EM_PRODUCAO', 'ENTREGUE')
  NOT NULL DEFAULT 'PENDENTE' AFTER dtentregaitvenda;

ALTER TABLE itvenda
  ADD COLUMN nrmesa VARCHAR(50) NULL AFTER idcontrolebar;
