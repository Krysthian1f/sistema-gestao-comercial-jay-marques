# Sistema de Gestão Comercial Jay Marques

Aplicação web em português brasileiro para apoiar a organização comercial da Jay Marques. O projeto utiliza Flask e SQLite e está sendo desenvolvido por etapas para a Experiência Prática III.

## Objetivo

Reunir as operações comerciais em uma interface responsiva, com acesso administrativo protegido e dados persistidos localmente. Esta versão já permite à proprietária autenticar-se e administrar o catálogo e o estoque.

## Funcionalidades disponíveis

- Login administrativo exclusivo, sem cadastro público de usuários.
- Senhas armazenadas somente como hash; criação inicial da conta por prompt oculto no terminal.
- Proteção de rotas internas, token CSRF em operações de escrita e bloqueio temporário após cinco tentativas inválidas.
- Cadastro, pesquisa, edição e remoção confirmada de produtos.
- Código sequencial automático, categoria, descrição, preços, saldo e estoque mínimo.
- Registro de entradas e saídas com motivo, histórico de movimentações e bloqueio de saídas acima do saldo.
- Alertas de estoque baixo e total de produtos ativos no dashboard.
- Temas claro e escuro, controles de fonte, suporte a teclado e rótulos para leitores de tela.
- Interface responsiva com a logomarca Marques Stores fornecida para o projeto.

Clientes, vendas, financeiro e relatórios ainda não possuem rotas e telas funcionais. Os indicadores correspondentes no dashboard são apresentados como indisponíveis, sem dados fictícios.

## Tecnologias

- Python 3.12.
- Flask, Flask-Login, Flask-SQLAlchemy e SQLAlchemy.
- SQLite.
- HTML, CSS, JavaScript e Bootstrap 5.
- pytest e pytest-cov.

## Estrutura do projeto

```text
app/
├── auth/                 # Login, logout e autenticação administrativa
├── dashboard/            # Dashboard e indicadores disponíveis
├── inventory/            # Movimentações de estoque
├── products/             # Catálogo de produtos
├── static/
│   ├── css/              # Identidade visual, temas e responsividade
│   ├── img/              # Logomarca fornecida
│   └── js/               # Menu, preferências acessíveis e senha visível
└── templates/            # Layout, login, dashboard e produtos
config.py                 # Configurações Flask e SQLite
run.py                    # Inicialização local
tests/                    # Testes de autenticação, integração e produtos
.github/workflows/ci.yml  # Testes e cobertura no GitHub Actions
```

## Instalação no Windows

Requisitos: Python 3.12 e PowerShell.

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### Criar a conta administrativa

Na primeira execução, crie a única conta administrativa:

```powershell
python -m flask --app run.py create-admin
```

O comando usa o nome de usuário `vida` e solicita a senha duas vezes, sem exibi-la no terminal. A senha precisa ter pelo menos 12 caracteres e é salva no SQLite somente como hash. O comando não cria outra conta nem redefine uma conta existente. Não há cadastro público.

### Executar

```powershell
python run.py
```

Abra [http://127.0.0.1:5000/login](http://127.0.0.1:5000/login) e entre com o usuário `vida` e a senha definida no passo anterior. Após cinco tentativas inválidas, o acesso fica bloqueado por 15 minutos.

## Configuração de segurança

No ambiente local HTTP, o cookie `Secure` fica desativado para permitir a sessão em `localhost`. Em produção, use HTTPS, defina uma chave `SECRET_KEY` aleatória e estável por variável de ambiente e configure `SESSION_COOKIE_SECURE=1`. Nunca publique `.env`, chaves, senhas ou a pasta `instance/`.

O SQLite local fica em `instance/` e é ignorado pelo Git. A inicialização cria tabelas ausentes sem apagar registros existentes. Os testes utilizam bancos temporários e não acessam o banco local.

## Testes

Com o ambiente virtual ativado:

```powershell
python -m pytest
```

Para medir cobertura:

```powershell
python -m pytest --cov=app --cov-report=term-missing
```

## Integração contínua

O GitHub Actions instala as dependências em Python 3.12 e executa a suíte pytest com cobertura em cada push e Pull Request direcionado a `main`. Não são necessárias credenciais para o pipeline.
