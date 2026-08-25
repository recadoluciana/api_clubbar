-- Corrige leads antigos que ja tiveram atendimento antes da automatizacao do pipeline.
UPDATE leadparceiro l
SET l.status = 'NEGOCIANDO'
WHERE l.status = 'NOVO'
  AND EXISTS (
    SELECT 1
    FROM leadagendamento a
    WHERE a.leadparceiro_id = l.leadparceiro_id
  );

UPDATE leadparceiro l
SET l.status = 'CONTATADO'
WHERE l.status = 'NOVO'
  AND EXISTS (
    SELECT 1
    FROM leadmensagem m
    WHERE m.leadparceiro_id = l.leadparceiro_id
      AND m.origem = 'CLUBBAR'
      AND m.mensagem <> 'Ola! Recebemos seu interesse. Use este portal para conversar com nossa equipe e acompanhar os proximos passos.'
  );
