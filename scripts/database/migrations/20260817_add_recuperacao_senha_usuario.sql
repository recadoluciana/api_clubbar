CREATE TABLE IF NOT EXISTS usuariosenha (
  usuariosenha_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  usuario_id BIGINT NOT NULL,
  codigohash VARCHAR(255) NOT NULL,
  expiracao DATETIME NOT NULL,
  usado CHAR(1) NOT NULL DEFAULT 'N',
  dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_usuariosenha_usuario (usuario_id),
  CONSTRAINT fk_usuariosenha_usuario
    FOREIGN KEY (usuario_id) REFERENCES usuario(usuario_id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;
