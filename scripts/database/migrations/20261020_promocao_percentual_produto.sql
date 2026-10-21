-- Promoções percentuais substituem a roleta: o parceiro informa diretamente
-- o desconto aplicado ao produto, sem sorteio nem prazo de resgate.
ALTER TABLE beneficioprodutocampanha
  ADD COLUMN percentual_desconto DECIMAL(5,2) NULL AFTER vrpacote;
