CREATE TABLE eventomodelo (
  eventomodelo_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  organizacao_id BIGINT NOT NULL, loja_id BIGINT NOT NULL,
  nmtituloevento VARCHAR(120) NOT NULL,
  dsdescevento TEXT NULL, dspoliticacancelamento TEXT NULL,
  dspoliticareembolso TEXT NULL, dspoliticacashback TEXT NULL,
  nmlocalevento VARCHAR(120) NULL, dsendlocevento VARCHAR(200) NULL,
  urlbannerevento VARCHAR(255) NULL, urlmapaingressos VARCHAR(255) NULL,
  dsmapaingressos VARCHAR(255) NULL,
  vrprecolote DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  qttotallote INT NULL,
  statusevento ENUM('ATIVO','INATIVO') NOT NULL DEFAULT 'ATIVO',
  dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_eventomodelo_organizacao FOREIGN KEY (organizacao_id) REFERENCES organizacao(organizacao_id),
  CONSTRAINT fk_eventomodelo_loja FOREIGN KEY (loja_id) REFERENCES loja(loja_id),
  INDEX idx_eventomodelo_org_loja_status (organizacao_id, loja_id, statusevento)
) ENGINE=InnoDB DEFAULT CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
ALTER TABLE evento ADD COLUMN eventomodelo_id BIGINT NULL AFTER loja_id;
ALTER TABLE evento ADD INDEX idx_evento_modelo (eventomodelo_id);
ALTER TABLE evento ADD CONSTRAINT fk_evento_modelo FOREIGN KEY (eventomodelo_id) REFERENCES eventomodelo(eventomodelo_id) ON DELETE RESTRICT ON UPDATE CASCADE;

INSERT INTO eventomodelo (
  organizacao_id, loja_id, nmtituloevento, dsdescevento,
  dspoliticacancelamento, dspoliticareembolso, dspoliticacashback,
  nmlocalevento, dsendlocevento, urlbannerevento,
  urlmapaingressos, dsmapaingressos, statusevento, vrprecolote, qttotallote
)
SELECT e.organizacao_id, e.loja_id, e.nmtituloevento, d.dsdescevento,
       d.dspoliticacancelamento, d.dspoliticareembolso, d.dspoliticacashback,
       e.nmlocalevento, e.dsendlocevento, e.urlbannerevento,
       e.urlmapaingressos, e.dsmapaingressos,
       IF(e.statusevento='INATIVO','INATIVO','ATIVO'),
       COALESCE((SELECT l.vrprecolote FROM eventolote l WHERE l.evento_id=e.evento_id ORDER BY l.nrlote,l.lote_id LIMIT 1),0),
       (SELECT l.qttotallote FROM eventolote l WHERE l.evento_id=e.evento_id ORDER BY l.nrlote,l.lote_id LIMIT 1)
FROM evento e LEFT JOIN eventodescricao d ON d.evento_id=e.evento_id;

UPDATE evento e
JOIN eventomodelo m ON m.organizacao_id=e.organizacao_id AND m.loja_id=e.loja_id
  AND m.nmtituloevento=e.nmtituloevento
SET e.eventomodelo_id=m.eventomodelo_id
WHERE e.eventomodelo_id IS NULL;
