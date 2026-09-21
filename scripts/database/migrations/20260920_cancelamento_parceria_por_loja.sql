CREATE TABLE IF NOT EXISTS cancelamentoparceria (
  cancelamentoparceria_id BIGINT NOT NULL AUTO_INCREMENT,
  loja_id BIGINT NOT NULL,
  justificativa TEXT NOT NULL,
  dtsolicitacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtavisoate DATETIME NOT NULL,
  sitcancelamento VARCHAR(20) NOT NULL DEFAULT 'SOLICITADO',
  PRIMARY KEY (cancelamentoparceria_id),
  UNIQUE KEY uq_cancelamento_parceria_loja (loja_id),
  CONSTRAINT fk_cancelamento_parceria_loja FOREIGN KEY (loja_id) REFERENCES loja(loja_id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
