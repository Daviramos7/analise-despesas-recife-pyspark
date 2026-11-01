-- Mini star schema com valores redondos, para conferir a API "na mão".
drop schema if exists marts cascade;
create schema marts;

create table marts.dim_mes (sk_mes int, ano int, mes int, ano_mes text);
insert into marts.dim_mes values (202301, 2023, 1, '2023-01'), (202302, 2023, 2, '2023-02');

create table marts.dim_unidade (sk_unidade int, unidade_codigo text, unidade_nome text,
                                orgao_codigo text, orgao_nome text);
insert into marts.dim_unidade values
  (1, '48.01', 'FMS', '48', 'SECRETARIA DE SAÚDE'),
  (2, '14.01', 'SEDUC', '14', 'SECRETARIA DE EDUCAÇÃO');

create table marts.dim_credor (sk_credor int, credor_codigo text, credor_nome text,
                               credor_informado boolean);
insert into marts.dim_credor values
  (1, '0', 'CREDOR NÃO INFORMADO', false),
  (2, '111', 'EMPRESA A', true),
  (3, '222', 'EMPRESA A', true),   -- mesmo nome, outro código: deve consolidar
  (4, '333', 'EMPRESA B', true);

create table marts.dim_classif_funcional (sk_classif_funcional int, funcao_codigo text, funcao_nome text);
insert into marts.dim_classif_funcional values (1, '10', 'SAÚDE'), (2, '12', 'EDUCAÇÃO');

create table marts.dim_classif_economica (sk_classif_economica int, modalidade_aplicacao_codigo text);
insert into marts.dim_classif_economica values (1, '90'), (2, '91');

create table marts.fato_despesa_movimento (
  sk_unidade int, sk_credor int, sk_mes int, sk_classif_economica int, sk_classif_funcional int,
  valor_empenhado numeric(18,2), valor_liquidado numeric(18,2), valor_pago numeric(18,2));
insert into marts.fato_despesa_movimento values
  -- saúde: jan 100, fev 300  | educação: jan 100, fev -50 (anulação) + 50 intra
  (1, 2, 202301, 1, 1, 100, 100,  80),
  (1, 3, 202302, 1, 1, 300, 300, 300),
  (2, 4, 202301, 1, 2, 100, 100, 100),
  (2, 1, 202302, 1, 2, -50, -50, -50),
  (2, 4, 202302, 2, 2,  50,  50,  50);

create table marts.dim_classif_receita (sk_classif_receita int, categoria_receita_nome text,
  origem_nome text, alinea_codigo text, alinea_nome text, intraorcamentaria boolean);
insert into marts.dim_classif_receita values
  (1, 'RECEITAS CORRENTES', 'IMPOSTOS', '50', 'IMPOSTO SOBRE A PROPRIEDADE PREDIAL E TERRITORIAL URBANA', false),
  (2, 'RECEITAS CORRENTES', 'IMPOSTOS', '51', 'IMPOSTOS SOBRE SERVIÇOS', false),
  (3, 'RECEITAS CORRENTES INTRAORÇAMENTÁRIAS', 'CONTRIBUIÇÕES', '99', 'PATRONAL INTRA', true);

create table marts.fato_receita_movimento (sk_unidade int, sk_mes int, sk_classif_receita int,
  valor_previsto_atualizado numeric(18,2), valor_arrecadado numeric(18,2));
insert into marts.fato_receita_movimento values
  (1, 202301, 1, 500, 200),
  (1, 202302, 2, 500, 400),
  (1, 202302, 3,   0,  50);
