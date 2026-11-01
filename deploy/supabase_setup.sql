-- Configuração do banco online (Supabase). Idempotente: pode rodar mais de uma vez.
-- Rodar como o usuário dono (postgres) ANTES da carga de dados.

-- 1) Tabela de feedback (mesmo DDL de src/orcamento/feedback.py)
create schema if not exists app;
create table if not exists app.interacoes (
    id           bigserial primary key,
    criado_em    timestamptz not null default now(),
    modelo       text not null,
    pergunta     text not null,
    resposta     text not null,
    chamadas     jsonb not null,
    numeros_sem_suporte jsonb not null,
    avaliacao    smallint check (avaliacao in (-1, 1)),
    comentario   text
);

-- 2) Usuário do app público: só LÊ os marts e só GRAVA feedback.
--    Criado sem login; a senha é definida pelo dono no painel do Supabase:
--      alter role app_web with login password '...';
do $$ begin
  if not exists (select from pg_roles where rolname = 'app_web') then
    create role app_web nologin;
  end if;
end $$;

grant usage on schema app to app_web;
grant insert on app.interacoes to app_web;
grant select (id), update (avaliacao, comentario) on app.interacoes to app_web;
grant usage on sequence app.interacoes_id_seq to app_web;

-- 3) Leitura dos marts. O dbt recria as tabelas a cada execução, então um GRANT simples
--    se perderia; o DEFAULT PRIVILEGES vale para toda tabela que o postgres criar no schema.
create schema if not exists marts;
grant usage on schema marts to app_web;
alter default privileges for role postgres in schema marts grant select on tables to app_web;
grant select on all tables in schema marts to app_web;
