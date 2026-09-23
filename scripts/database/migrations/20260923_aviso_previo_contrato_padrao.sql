UPDATE contratopadrao
SET conteudomodelo = REPLACE(
  conteudomodelo,
  'Este contrato vigora por prazo indeterminado e pode ser encerrado por qualquer parte, sem prejuízo das obrigações já constituídas.',
  'Este contrato vigora por prazo indeterminado e pode ser encerrado por qualquer parte, sem prejuízo das obrigações já constituídas. Com aviso prévio de 30 dias.'
)
WHERE conteudomodelo LIKE '%11. SUSPENSÃO E ENCERRAMENTO%'
  AND conteudomodelo LIKE '%Este contrato vigora por prazo indeterminado e pode ser encerrado por qualquer parte, sem prejuízo das obrigações já constituídas.%'
  AND conteudomodelo NOT LIKE '%Com aviso prévio de 30 dias.%';
