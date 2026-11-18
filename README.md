# Sistema de Gestão Comercial Jay Marques

Aplicação web em português brasileiro para apoiar a gestão comercial da Jay Marques. O projeto usa Flask, SQLite no ambiente local e PostgreSQL em produção.

## Objetivo

Reunir as operações comerciais em uma interface responsiva, com acesso direto ao painel (sem login), registros integrados e dados persistidos.

## Funcionalidades disponíveis

- Acesso direto ao painel, sem tela de login, sem usuário e sem senha.
- Token CSRF em todas as operações de escrita (POST/PUT/PATCH/DELETE).
- Cadastro, pesquisa, edição e remoção confirmada de produtos.
- Código sequencial automático, categoria, descrição, preços, saldo e estoque mínimo.
- Registro de entradas e saídas com motivo, histórico de movimentações e bloqueio de saídas acima do saldo.
- Cadastro, pesquisa, edição, histórico de compras e remoção lógica de clientes. Telefones normalizados evitam duplicidade.
- Registro de vendas com itens e preços históricos, cliente opcional, forma de pagamento, total calculado no servidor, baixa de estoque e proteção contra reenvio duplicado.
- Lançamentos financeiros de receitas e despesas, recebimentos de vendas vinculados automaticamente, filtros por período, saldo e lucro estimado após custo dos produtos e despesas.
- Relatórios de vendas, produtos, estoque e financeiro com filtros de data e exportação CSV.
- Dashboard com indicadores reais de produtos, clientes, vendas, faturamento, saldo financeiro e atividade recente.
- Rota pública `/health` para monitoramento de disponibilidade e conexão ao banco.
- Alertas de estoque baixo e total de produtos ativos no dashboard.
- Temas claro e escuro, controles de fonte, suporte a teclado e rótulos para leitores de tela.
- Interface responsiva com a logomarca Marques Stores fornecida para o projeto.

O sistema não possui autenticação: qualquer pessoa com acesso à URL entra diretamente no painel. Por isso, mantenha o endereço restrito a pessoas de confiança e não o divulgue publicamente. Os lançamentos financeiros são registros auditáveis e não podem ser editados ou excluídos pela interface.

## Tecnologias

- Python 3.12.
- Flask, Flask-SQLAlchemy e SQLAlchemy.
- SQLite no ambiente local e PostgreSQL como opção recomendada para produção.
- Gunicorn e psycopg 3 para execução no Render com PostgreSQL Neon.
- HTML, CSS, JavaScript e Bootstrap 5.
- pytest e pytest-cov.

## Estrutura do projeto

```text
app/
├── customers/            # Cadastro e consulta de clientes
├── dashboard/            # Dashboard e indicadores reais
├── finance/              # Receitas, despesas e resumo financeiro
├── inventory/            # Movimentações de estoque
├── products/             # Catálogo de produtos
├── reports/              # Relatórios e exportação CSV
├── sales/                # Vendas, itens e atualização do estoque
├── static/
│   ├── css/              # Identidade visual, temas e responsividade
│   ├── img/              # Logomarca fornecida
│   └── js/               # Menu e preferências acessíveis
└── templates/            # Telas do sistema
config.py                 # Configuração Flask, SQLite e PostgreSQL
run.py                    # Inicialização local
init_neon_db.py           # Inicialização confirmada do esquema Neon
render.yaml               # Configuração do serviço Web no Render
Procfile                  # Comando web compatível com plataformas PaaS
testar_neon.py            # Verificação somente leitura da conexão Neon
tests/                    # Testes de segurança e dos módulos comerciais
.github/workflows/ci.yml  # Testes e cobertura no GitHub Actions
```

## Instalação no Windows

Requisitos: Python 3.12 e PowerShell.

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### Acesso ao sistema

O sistema abre diretamente no painel. Não existe tela de login, conta administrativa,
usuário ou senha.

### Executar

```powershell
python run.py
```

Abra [http://127.0.0.1:5000/](http://127.0.0.1:5000/) e use o sistema diretamente.

## Configuração de segurança

No ambiente local HTTP, o cookie `Secure` fica desativado para permitir a sessão em `localhost`. Em produção, use HTTPS, defina uma chave `SECRET_KEY` aleatória e estável por variável de ambiente e configure `SESSION_COOKIE_SECURE=1`. A sessão é usada apenas para o token CSRF, não para autenticação. Nunca publique `.env`, chaves, senhas ou a pasta `instance/`.

O SQLite local fica em `instance/` e é ignorado pelo Git. A inicialização cria tabelas ausentes sem apagar registros existentes. Os testes utilizam bancos temporários e não acessam o banco local.

## Preparar a publicação no Render + Neon

O `render.yaml` configura um serviço Web Python no Render. O `Procfile` mantém o mesmo comando de inicialização para plataformas que leem esse formato. A configuração atual desativa o deploy automático; após conectar o repositório, revise e inicie o deploy manualmente no painel.

### Banco Neon e variáveis de ambiente

1. No Console do Neon, abra **Connect** e selecione a branch, o database e a role corretos. Copie a connection string PostgreSQL com TLS; mantenha os parâmetros fornecidos pelo Neon, incluindo `sslmode=require`.
2. No Render, crie ou conecte um Web Service/Blueprint usando a raiz deste repositório e o `render.yaml`.
3. Cadastre `DATABASE_URL` como secret no painel do Render. No Blueprint, `sync: false` deixa o valor fora do YAML e exige que ele seja informado no painel durante a criação inicial; para serviços já existentes, confira ou cadastre-o manualmente. Nunca coloque essa URL no código, README ou `.env` versionado.

Quando `DATABASE_URL` estiver configurada, a aplicação usa PostgreSQL através de psycopg 3. Sem ela, a configuração local continua usando SQLite em `instance/`. Este processo não migra dados do SQLite.

### Configuração do serviço Render

O Blueprint define instalação, inicialização, variáveis e health check:

- **Runtime:** Python.
- **Build command:** `pip install -r requirements.txt`.
- **Start command:** `gunicorn --bind 0.0.0.0:$PORT run:app`.
- **Python:** `3.12.11`, fixado por `PYTHON_VERSION` no Blueprint e `.python-version`.
- **Health check:** `GET /health`; a rota retorna HTTP 200 quando o banco responde e HTTP 503 quando a consulta ao banco falha.
- **Auto deploy:** desligado no Blueprint; faça deploy manual após revisar a configuração.

O Render disponibiliza `PORT` para o Web Service, com padrão documentado `10000`. O Gunicorn escuta em `0.0.0.0:$PORT`, conforme exigido para receber tráfego externo. [Portas dos Web Services](https://render.com/docs/web-services)

O `render.yaml` configura `APP_ENV=production`, `SESSION_COOKIE_SECURE=true` e `SECRET_KEY` com `generateValue: true`. O Render gera uma chave aleatória para o serviço. Não substitua esse valor por uma chave fixa publicada no repositório. A aplicação recusa iniciar em produção sem `SECRET_KEY`.

### Inicializar o esquema Neon

Em produção, a aplicação não cria tabelas no startup. O esquema é inicializado explicitamente por `init_neon_db.py`, que valida o host pooler, o database `neondb`, TLS e o esquema atual antes de solicitar confirmação. O script cria somente tabelas ausentes; não migra registros, não apaga tabelas e não altera tabelas existentes. Use uma estratégia de migração separada para alterações de colunas ou constraints.

Antes de inicializar, configure `DATABASE_URL` de forma segura em um terminal local ou console interativo autorizado, sem gravá-la em arquivo, e execute:

```powershell
python init_neon_db.py
```

Confira o host, o database e a lista de tabelas ausentes; digite `CRIAR TABELAS NO NEON` somente após conferir o destino. O modo `--preflight-only` permite listar o destino e o estado das tabelas sem criar nada:

```powershell
python init_neon_db.py --preflight-only
```

### Passos para publicar

1. No Render, conecte o repositório GitHub Jay Marques e escolha a branch e a raiz corretas.
2. Use o Blueprint existente para carregar `render.yaml`; confira runtime, comandos e health check antes de criar o serviço.
3. Informe `DATABASE_URL` como secret do Render. Confirme também `APP_ENV`, `SECRET_KEY` e `SESSION_COOKIE_SECURE` no painel.
4. Antes de depender da aplicação, confirme que o database Neon contém as tabelas necessárias.
5. Revise as mudanças e inicie o deploy manualmente. Depois, verifique `/health` e `/` no endereço do serviço.

Consulte a documentação oficial do [Blueprint YAML](https://render.com/docs/blueprint-spec), [variáveis e secrets](https://render.com/docs/configure-environment-variables), [versão do Python](https://render.com/docs/python-version), [health checks](https://render.com/docs/health-checks) e [deploy de Flask](https://render.com/docs/deploy-flask). Para Neon, consulte [conexões PostgreSQL](https://neon.com/docs/connect/connect-from-any-app) e [SQLAlchemy](https://neon.com/docs/guides/sqlalchemy).

## Testes

Com o ambiente virtual ativado:

```powershell
python -m pytest
```

Para medir cobertura:

```powershell
python -m pytest --cov=app --cov-report=term-missing
```

Os testes criam banco SQLite temporário isolado e não abrem nem alteram `instance/gestao_comercial.sqlite`. Testes de PostgreSQL/Neon exigem credenciais e conexão externas e, por isso, não são executados pela suíte local/CI. A rota `/health` pode ser usada por um monitor HTTP sem autenticação; retorna HTTP 200 quando o processo consegue consultar o banco e HTTP 503 quando não consegue.

## Integração contínua

O GitHub Actions instala as dependências em Python 3.12 e executa a suíte pytest com cobertura em cada push e Pull Request direcionado a `main`. Não são necessárias credenciais para o pipeline.
