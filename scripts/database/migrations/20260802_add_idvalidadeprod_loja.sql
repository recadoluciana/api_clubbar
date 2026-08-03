ALTER TABLE loja
  ADD COLUMN idvalidadeprod CHAR(1) NOT NULL DEFAULT 'S'
  AFTER nrdiavalidade;

ALTER TABLE loja
  ADD CONSTRAINT chk_idvalidadeprod
  CHECK (idvalidadeprod IN ('S', 'N'));
