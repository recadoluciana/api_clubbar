ALTER TABLE leadparceiro
  MODIFY status ENUM('NOVO','CONTATADO','NEGOCIANDO','APROVADO_CADASTRO','CONVERTIDO','PERDIDO') NOT NULL DEFAULT 'NOVO';

ALTER TABLE organizacao
  MODIFY rzsocialorganizacao VARCHAR(160) NULL,
  MODIFY cnpjorganizacao VARCHAR(14) NULL,
  MODIFY endorganizacao VARCHAR(255) NULL,
  MODIFY nrendorganizacao VARCHAR(20) NULL,
  MODIFY estado_id BIGINT NULL,
  ADD COLUMN nmresponsavelprincipal VARCHAR(120) NULL AFTER telorganizacao,
  ADD COLUMN tipooperacao VARCHAR(30) NULL AFTER nmresponsavelprincipal;

ALTER TABLE loja
  MODIFY nrceploja VARCHAR(9) NULL,
  MODIFY nrendeloja VARCHAR(20) NULL,
  MODIFY estado_id BIGINT NULL,
  ADD COLUMN tipoloja VARCHAR(30) NULL AFTER nmloja,
  ADD COLUMN atendimentofisico CHAR(1) NOT NULL DEFAULT 'S' AFTER tipoloja,
  ADD COLUMN vendaprodutos CHAR(1) NOT NULL DEFAULT 'S' AFTER atendimentofisico,
  ADD COLUMN vendaingressos CHAR(1) NOT NULL DEFAULT 'S' AFTER vendaprodutos;

CREATE TABLE titularfinanceiro (
  titularfinanceiro_id BIGINT NOT NULL AUTO_INCREMENT,
  organizacao_id BIGINT NOT NULL,
  tipotitular ENUM('PF','PJ') NOT NULL,
  cpfcnpj VARCHAR(14) NOT NULL,
  nmrazaosocial VARCHAR(160) NOT NULL,
  nmfantasia VARCHAR(160) NULL,
  dtnascimento DATE NULL,
  email VARCHAR(255) NOT NULL,
  telefone VARCHAR(25) NOT NULL,
  cep VARCHAR(9) NOT NULL,
  endereco VARCHAR(255) NOT NULL,
  numero VARCHAR(20) NOT NULL,
  complemento VARCHAR(120) NULL,
  bairro VARCHAR(120) NOT NULL,
  cidade_id BIGINT NOT NULL,
  estado_id BIGINT NOT NULL,
  vrfaturamentomensal DECIMAL(12,2) NOT NULL DEFAULT 0,
  asaas_account_id VARCHAR(100) NULL,
  asaas_wallet_id VARCHAR(100) NULL,
  asaas_api_key_criptografada TEXT NULL,
  status_asaas VARCHAR(30) NOT NULL DEFAULT 'NAO_INICIADO',
  onboarding_url TEXT NULL,
  dtultimaverificacao DATETIME NULL,
  dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (titularfinanceiro_id),
  UNIQUE KEY uq_titularfinanceiro_organizacao (organizacao_id),
  CONSTRAINT fk_titularfinanceiro_organizacao FOREIGN KEY (organizacao_id)
    REFERENCES organizacao (organizacao_id) ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT fk_titularfinanceiro_cidade FOREIGN KEY (cidade_id) REFERENCES cidade (cidade_id),
  CONSTRAINT fk_titularfinanceiro_estado FOREIGN KEY (estado_id) REFERENCES estado (estado_id)
);
