# Sistema de Gestão Comercial Jay Marques

Aplicação web em português brasileiro para apoiar a gestão comercial da Jay Marques. O projeto está sendo desenvolvido por etapas; esta versão entrega a estrutura Flask, o painel inicial e a configuração do banco local.

## Tecnologias

- Python 3.12
- Flask 3.x com padrão de fábrica de aplicação e Blueprint
- Flask-SQLAlchemy e SQLAlchemy
- Flask-Login (extensão configurada; telas e rotas de acesso entram na Fase 2)
- SQLite
- HTML5, CSS3, JavaScript e Bootstrap 5.3

## Estado do projeto

### Fase 1 — concluída

- Configuração centralizada em `config.py`.
- Extensões e fábrica de aplicação em `app/extensions.py` e `app/__init__.py`.
- Banco SQLite local criado em `instance/gestao_comercial.sqlite`.
- Painel responsivo, navegação lateral e identidade visual Jay Marques.
- Data apresentada no formato `DD/MM/AAAA` e fuso horário de São Paulo.

Os módulos de produtos, estoque, clientes, vendas, indicadores financeiros, autenticação de telas, relatórios e exportação ainda não foram implementados. O painel não exibe dados fictícios.

## Executar no Windows

Na pasta do projeto, crie e ative um ambiente virtual com Python 3.12:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python run.py
```

Abra http://127.0.0.1:5000 no navegador. O banco SQLite e uma chave de sessão gerada aleatoriamente são criados na pasta `instance/` na primeira execução. Para configurar uma chave própria, defina a variável de ambiente `SECRET_KEY` antes de iniciar o servidor.

## Configuração

- `SECRET_KEY`: chave de sessão opcional. Se ausente, é gerada e armazenada localmente em `instance/.secret_key`.
- `DATABASE_URL`: URI SQLAlchemy opcional; por padrão, usa SQLite em `instance/gestao_comercial.sqlite`.

## Próximas etapas

A Fase 2 depende de autorização para iniciar. Ainda não há modelo de usuário, administrador padrão ou tela de acesso.
