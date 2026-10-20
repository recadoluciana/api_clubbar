-- O cardápio pode ficar publicado para consulta sem permitir compras pelo app.
-- Mantém as associações existentes habilitadas para não interromper operações.
ALTER TABLE cardapioloja
ADD COLUMN IF NOT EXISTS vendas_habilitadas TINYINT(1) NOT NULL DEFAULT 1
AFTER sitassociacao;
