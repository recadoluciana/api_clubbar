-- Remodelagem destrutiva autorizada: remove dados de eventos/vendas para criar estoque compartilhado.
SET FOREIGN_KEY_CHECKS = 0;
DELETE FROM checkout_asaas_item;
DELETE FROM checkout_asaas;
DELETE FROM reserva_ingresso_participante;
DELETE FROM reserva_ingresso;
DELETE FROM itvenda WHERE tipoitem = 'INGRESSO';
DELETE FROM eventoatracao;
DELETE FROM eventolote;
DELETE FROM eventosetor;
DELETE FROM evento;
SET FOREIGN_KEY_CHECKS = 1;

ALTER TABLE eventolote DROP COLUMN tipoingresso, DROP COLUMN vrprecolote;
CREATE TABLE eventolotepreco (
  lotepreco_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  lote_id BIGINT NOT NULL, nmpreco VARCHAR(100) NOT NULL,
  tipopreco VARCHAR(30) NOT NULL, vrpreco DECIMAL(10,2) NOT NULL,
  aplicacotalegal BOOLEAN NOT NULL DEFAULT FALSE,
  exigecomprovante BOOLEAN NOT NULL DEFAULT FALSE,
  situacao VARCHAR(10) NOT NULL DEFAULT 'ATIVO', nrordem INT NOT NULL DEFAULT 1,
  dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_lotepreco_tipo (lote_id, tipopreco),
  CONSTRAINT fk_lotepreco_lote FOREIGN KEY (lote_id) REFERENCES eventolote(lote_id) ON DELETE CASCADE,
  CHECK (vrpreco >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
ALTER TABLE reserva_ingresso ADD lotepreco_id BIGINT NOT NULL AFTER lote_id, ADD tipobeneficio VARCHAR(30) NULL AFTER lotepreco_id, ADD CONSTRAINT fk_reserva_lotepreco FOREIGN KEY (lotepreco_id) REFERENCES eventolotepreco(lotepreco_id);
ALTER TABLE itvenda ADD lotepreco_id BIGINT NULL AFTER lote_id, ADD tipobeneficio VARCHAR(30) NULL AFTER lotepreco_id, ADD CONSTRAINT fk_itvenda_lotepreco FOREIGN KEY (lotepreco_id) REFERENCES eventolotepreco(lotepreco_id);
ALTER TABLE eventomodelo DROP COLUMN qttotallote;
