CREATE TABLE IF NOT EXISTS auditoria (
  auditoria_id BIGINT NOT NULL AUTO_INCREMENT,
  tabela VARCHAR(100) NOT NULL,
  registro_id VARCHAR(255) NOT NULL,
  acao VARCHAR(15) NOT NULL,
  ator_tipo VARCHAR(20) NOT NULL DEFAULT 'SISTEMA',
  ator_id VARCHAR(100) NULL,
  usuario_id BIGINT NULL,
  operador_id BIGINT NULL,
  ator_nome VARCHAR(200) NOT NULL,
  ator_email VARCHAR(200) NULL,
  dados_anteriores JSON NULL,
  dados_novos JSON NULL,
  metodo_http VARCHAR(10) NULL,
  rota VARCHAR(500) NULL,
  dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

  PRIMARY KEY (auditoria_id),
  INDEX idx_auditoria_registro (tabela, registro_id, dtcriacao),
  INDEX idx_auditoria_usuario (usuario_id, dtcriacao),
  INDEX idx_auditoria_operador (operador_id, dtcriacao),
  CONSTRAINT fk_auditoria_usuario FOREIGN KEY (usuario_id)
    REFERENCES usuario(usuario_id) ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT fk_auditoria_operador FOREIGN KEY (operador_id)
    REFERENCES operador(operador_id) ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT chk_auditoria_acao
    CHECK (acao IN ('INCLUSAO', 'ALTERACAO', 'EXCLUSAO')),
  CONSTRAINT chk_auditoria_ator_tipo
    CHECK (ator_tipo IN ('USUARIO', 'OPERADOR', 'CLIENTE', 'LEAD', 'SISTEMA'))
) ENGINE=InnoDB DEFAULT CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
