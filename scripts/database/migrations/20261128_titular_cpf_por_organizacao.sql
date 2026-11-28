-- Permite o mesmo CPF/CNPJ em organizações distintas, sem duplicá-lo dentro
-- da mesma organização. Não altera titulares nem contas de recebimento.
ALTER TABLE titularfinanceiro
  DROP INDEX uk_titularfinanceiro_cpfcnpj,
  ADD UNIQUE KEY uk_titularfinanceiro_org_cpfcnpj (organizacao_id, cpfcnpj);
