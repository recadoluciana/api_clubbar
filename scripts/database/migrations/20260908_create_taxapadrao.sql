CREATE TABLE IF NOT EXISTS taxapadrao (
  taxapadrao_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  nrversao BIGINT NOT NULL,
  pctaxaproduto DECIMAL(10,2) NOT NULL,
  pctaxaingresso DECIMAL(10,2) NOT NULL,
  vrtaxaminimaingresso DECIMAL(10,2) NOT NULL DEFAULT 0,
  sittaxapadrao VARCHAR(15) NOT NULL DEFAULT 'RASCUNHO',
  dtiniciovigencia DATETIME NULL,
  dtfimvigencia DATETIME NULL,
  dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_taxapadrao_versao (nrversao),
  INDEX idx_taxapadrao_situacao (sittaxapadrao),
  CONSTRAINT ck_taxapadrao_situacao CHECK (sittaxapadrao IN ('RASCUNHO','VIGENTE','ENCERRADA'))
) ENGINE=InnoDB DEFAULT CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO taxapadrao (nrversao, pctaxaproduto, pctaxaingresso, vrtaxaminimaingresso, sittaxapadrao, dtiniciovigencia)
SELECT 1, 5.00, 10.00, 2.99, 'VIGENTE', CURRENT_TIMESTAMP
WHERE NOT EXISTS (SELECT 1 FROM taxapadrao);

ALTER TABLE leadestabelecimento ADD COLUMN vrtaxaminimaingresso DECIMAL(10,2) NOT NULL DEFAULT 0 AFTER vrtaxaing;
ALTER TABLE loja ADD COLUMN vrtaxaminimaingresso DECIMAL(10,2) NOT NULL DEFAULT 0 AFTER vrtaxaing;
ALTER TABLE leadestabelecimentocontrato ADD COLUMN taxapadrao_id BIGINT NULL AFTER contratopadrao_id;
ALTER TABLE leadestabelecimentocontrato ADD COLUMN vrtaxaminimaingresso DECIMAL(10,2) NOT NULL DEFAULT 0 AFTER vrtaxaing;
ALTER TABLE leadestabelecimentocontrato ADD CONSTRAINT fk_leadcontrato_taxapadrao FOREIGN KEY (taxapadrao_id) REFERENCES taxapadrao(taxapadrao_id);
