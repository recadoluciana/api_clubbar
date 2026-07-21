INSERT INTO organizacao (
    nmorganizacao,
    rzsocialorganizacao,
    cnpjorganizacao,
    emailorganizacao,
    telorganizacao,
    ceporganizacao,
    endorganizacao,
    nrendorganizacao,
    complorganizacao,
    cidade_id,
    nmbairro,
    sitorganizacao
)
VALUES (
    'Clubbar',
    'Triluco Ltda',
    '97700731000181',
    'suporte@clubbar.com.br',
    '35999999999',
    '37185054',
    'Rua 7 de Setembro',
    '353',
    'Laboratório Breyner',
    3059,
    'Centro',
    'ATIVA'
);

INSERT INTO usuario (
    organizacao_id,
    loja_id,
    nmusuario,
    emailuser,
    senhahashuser,
    dscargo,
    situsuario
)
VALUES (
    1,
    NULL,
    'Administrador Clubbar',
    'recadoluciana@gmail.com',
    '1',
    'SUPERADMIN',
    'ATIVO'
);