UPDATE coraduvida
SET resposta = 'Acesse Perfil/Minhas compras, localize a compra e toque em Cancelar compra. As condições de cancelamento aplicáveis serão exibidas antes da confirmação.',
    idordem = 4,
    sitduvida = 'ATIVA'
WHERE pergunta = 'Como cancelar a compra de um ingresso?';

UPDATE coraduvida
SET resposta = 'Acesse Perfil/Minhas compras, localize a compra e toque em Cancelar compra. O cancelamento pode ser solicitado até 7 dias após a data da compra, desde que o produto ainda não tenha sido retirado. Quando permitido, o reembolso é solicitado pelo mesmo meio de pagamento.',
    idordem = 11,
    sitduvida = 'ATIVA'
WHERE pergunta = 'Como cancelar a compra de um produto?';

INSERT INTO coraduvida (pergunta, resposta, idordem, sitduvida)
VALUES
    ('Preciso apresentar documento físico ou aceita digital?', 'Depende da política do organizador. Recomendamos confirmar antes do evento.', 12, 'ATIVA'),
    ('Posso comprar meia-entrada para outra pessoa?', 'Sim, mas essa pessoa precisará apresentar o documento dela no dia do evento.', 13, 'ATIVA'),
    ('O organizador pode limitar a quantidade de meia-entrada por CPF?', 'Sim, desde que respeite a cota mínima de 40% do total de ingressos.', 14, 'ATIVA'),
    ('Documento estrangeiro é aceito para comprovar idade (idosos)?', 'Sim, desde que seja documento oficial com foto. Passaporte, por exemplo, é aceito.', 15, 'ATIVA'),
    ('Perdi minha carteirinha de estudante. E agora?', 'Solicite a segunda via junto à entidade que emitiu o documento, como UNE ou UBES. O processo pode levar alguns dias.', 16, 'ATIVA')
ON DUPLICATE KEY UPDATE
    resposta = VALUES(resposta),
    idordem = VALUES(idordem),
    sitduvida = 'ATIVA';
