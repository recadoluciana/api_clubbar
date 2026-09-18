ALTER TABLE leadestabelecimentocontrato
  ADD COLUMN tipoinstrumento VARCHAR(20) NOT NULL DEFAULT 'ORIGINAL' AFTER leadestabelecimentocontrato_id,
  ADD COLUMN contratoorigem_id BIGINT NULL AFTER tipoinstrumento,
  ADD COLUMN nrretificacao INT NULL AFTER contratoorigem_id,
  ADD COLUMN dsjustificativa VARCHAR(500) NULL AFTER nrretificacao,
  ADD COLUMN mesmaparteconfirmada CHAR(1) NULL AFTER dsjustificativa,
  ADD CONSTRAINT fk_contrato_retificacao_origem FOREIGN KEY (contratoorigem_id)
    REFERENCES leadestabelecimentocontrato(leadestabelecimentocontrato_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD UNIQUE KEY uk_contrato_retificacao_numero (contratoorigem_id, nrretificacao);
