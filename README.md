# Sistema de Gestão Comercial Jay Marques

Este projeto está sendo criado para ajudar a organizar a rotina comercial da Jay Marques. A ideia é reunir, em um só lugar, informações sobre produtos, estoque, clientes, vendas e finanças.

## Como está o projeto

O sistema está em desenvolvimento. Hoje, já conta com uma aplicação Flask, um painel inicial responsivo e testes automatizados para a página principal e seus estados vazios. Quando ainda não há dados, o painel deixa isso claro em vez de mostrar números fictícios.

Os cadastros e as operações de produtos, estoque, clientes, vendas e financeiro ainda estão sendo construídos. Por isso, esta versão serve para desenvolvimento e demonstração; ainda não está pronta para controlar a operação real de uma loja.

## O que vem pela frente

- Cadastro de produtos e controle de estoque.
- Cadastro de clientes.
- Registro de vendas.
- Acompanhamento financeiro e relatórios.
- Acesso protegido para quem usa o sistema.

## Tecnologias

- Python 3.12 e Flask.
- SQLite com Flask-SQLAlchemy.
- HTML, CSS, JavaScript e Bootstrap.
- pytest para os testes automatizados.

## Como executar no Windows

Com Python 3.12 instalado, abra o PowerShell na pasta do projeto e execute:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python run.py
```

Depois, abra [http://127.0.0.1:5000](http://127.0.0.1:5000) no navegador.

## Como executar os testes

Com o ambiente virtual ativado, rode:

```powershell
python -m pytest
```

Os testes usam um banco SQLite temporário e preservam o banco local do projeto.

## Integração contínua

O GitHub Actions executa os testes a cada push e nos Pull Requests direcionados à branch `main`. O pipeline prepara o Python 3.12, instala as dependências e gera o relatório de cobertura com pytest-cov. Os testes usam bancos temporários; o workflow não precisa de senhas nem de chaves secretas.
