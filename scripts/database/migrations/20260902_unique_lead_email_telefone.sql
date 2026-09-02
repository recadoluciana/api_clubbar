ALTER TABLE leadparceiro
  ADD CONSTRAINT uq_leadparceiro_email_telefone UNIQUE (email, telefone);
