-- Preparação para associar contas Mercado Pago ao titular financeiro.
-- NÃO executar até que API e Partner tenham sido atualizados e validados juntos.
-- A migração não atribui automaticamente contas Mercado Pago existentes:
-- o titular deve ser confirmado pelo responsável pela organização.
-- Os registros de pagamento e as credenciais antigas não são excluídos.

ALTER TABLE lojamercadopago
  MODIFY COLUMN loja_id BIGINT NULL,
  ADD COLUMN titularfinanceiro_id BIGINT NULL,
  ADD INDEX idx_lojamercadopago_titular_ambiente (titularfinanceiro_id, ambiente),
  ADD UNIQUE KEY uq_lojamercadopago_titular_ambiente_usuario (titularfinanceiro_id, ambiente, mercadopago_user_id),
  ADD CONSTRAINT fk_lojamercadopago_titular_org
    FOREIGN KEY (organizacao_id, titularfinanceiro_id)
    REFERENCES titularfinanceiro (organizacao_id, titularfinanceiro_id);

CREATE TABLE IF NOT EXISTS titularmercadopagopendente (
  titularfinanceiro_id BIGINT NOT NULL,
  ambiente VARCHAR(20) NOT NULL,
  confirmacao_id VARCHAR(64) NOT NULL,
  credenciais TEXT NOT NULL,
  expira_em DATETIME NOT NULL,
  PRIMARY KEY (titularfinanceiro_id, ambiente),
  CONSTRAINT fk_mp_pendente_titular FOREIGN KEY (titularfinanceiro_id)
    REFERENCES titularfinanceiro (titularfinanceiro_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
