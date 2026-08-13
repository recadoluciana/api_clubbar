CREATE TABLE IF NOT EXISTS checkout_asaas_pagador (
  checkout_asaas_pagador_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  checkout_asaas_id BIGINT NOT NULL,
  venda_id BIGINT NULL,
  payment_id VARCHAR(100) NULL,
  asaas_customer_id VARCHAR(100) NULL,
  nome VARCHAR(150) NULL,
  cpf_cnpj VARCHAR(20) NULL,
  email VARCHAR(160) NULL,
  telefone VARCHAR(20) NULL,
  endereco VARCHAR(150) NULL,
  numero VARCHAR(20) NULL,
  complemento VARCHAR(80) NULL,
  bairro VARCHAR(80) NULL,
  cep VARCHAR(10) NULL,
  cidade VARCHAR(100) NULL,
  uf VARCHAR(2) NULL,
  dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu DATETIME NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_checkout_asaas_pagador_checkout (checkout_asaas_id),
  INDEX idx_checkout_asaas_pagador_venda (venda_id),
  INDEX idx_checkout_asaas_pagador_cpf_cnpj (cpf_cnpj),
  CONSTRAINT fk_checkout_asaas_pagador_checkout
    FOREIGN KEY (checkout_asaas_id) REFERENCES checkout_asaas(checkout_asaas_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_checkout_asaas_pagador_venda
    FOREIGN KEY (venda_id) REFERENCES venda(venda_id)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
