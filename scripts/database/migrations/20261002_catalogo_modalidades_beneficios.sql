-- Catálogo dinâmico de modalidades e benefícios de ingresso.
-- A aplicação executa uma migração idempotente equivalente no startup.
CREATE TABLE IF NOT EXISTS modalidadeingresso (
  modalidade_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  organizacao_id BIGINT NULL,
  cdmodalidade VARCHAR(40) NOT NULL UNIQUE,
  nmmodalidade VARCHAR(100) NOT NULL,
  tipomodalidade VARCHAR(20) NOT NULL DEFAULT 'COMERCIAL',
  aplicacotalegal BOOLEAN NOT NULL DEFAULT FALSE,
  exigebeneficio BOOLEAN NOT NULL DEFAULT FALSE,
  exigecomprovante BOOLEAN NOT NULL DEFAULT FALSE,
  permitepersonalizarnome BOOLEAN NOT NULL DEFAULT TRUE,
  situacao VARCHAR(10) NOT NULL DEFAULT 'ATIVO',
  nrordem INT NOT NULL DEFAULT 1,
  dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (organizacao_id) REFERENCES organizacao(organizacao_id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS beneficioingresso (
  beneficio_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  cdbeneficio VARCHAR(40) NOT NULL UNIQUE,
  nmbeneficio VARCHAR(100) NOT NULL,
  exigecomprovante BOOLEAN NOT NULL DEFAULT TRUE,
  situacao VARCHAR(10) NOT NULL DEFAULT 'ATIVO',
  nrordem INT NOT NULL DEFAULT 1,
  dtiniciovigencia DATETIME NULL,
  dtfimvigencia DATETIME NULL,
  dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu DATETIME NULL ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS modalidadebeneficio (
  modalidade_id BIGINT NOT NULL,
  beneficio_id BIGINT NOT NULL,
  dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (modalidade_id, beneficio_id),
  FOREIGN KEY (modalidade_id) REFERENCES modalidadeingresso(modalidade_id) ON DELETE CASCADE,
  FOREIGN KEY (beneficio_id) REFERENCES beneficioingresso(beneficio_id) ON DELETE RESTRICT
);
