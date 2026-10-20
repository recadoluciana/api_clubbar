-- Promoções do tipo "N unidades por R$ X" ficam independentes do cardápio.
ALTER TABLE beneficioprodutocampanha
  ADD COLUMN IF NOT EXISTS qtitenspacote INT NULL AFTER limite_cliente_dia,
  ADD COLUMN IF NOT EXISTS vrpacote DECIMAL(10,2) NULL AFTER qtitenspacote;

ALTER TABLE itcarrinho
  ADD COLUMN IF NOT EXISTS beneficioprodutocampanha_id BIGINT NULL,
  ADD KEY IF NOT EXISTS ix_itcarrinho_campanha (beneficioprodutocampanha_id);

ALTER TABLE itvenda
  ADD COLUMN IF NOT EXISTS beneficioprodutocampanha_id BIGINT NULL,
  ADD KEY IF NOT EXISTS ix_itvenda_campanha (beneficioprodutocampanha_id);

ALTER TABLE checkout_asaas_item
  ADD COLUMN IF NOT EXISTS beneficioprodutocampanha_id BIGINT NULL,
  ADD KEY IF NOT EXISTS ix_checkout_asaas_item_campanha (beneficioprodutocampanha_id);
