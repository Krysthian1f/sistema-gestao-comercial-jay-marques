def test_controles_acessiveis_estao_rotulados_e_disponiveis(client):
    page = client.get("/").get_data(as_text=True)

    assert 'role="group" aria-label="Controles de acessibilidade"' in page
    assert 'aria-label="Aumentar tamanho da fonte"' in page
    assert 'aria-label="Diminuir tamanho da fonte"' in page
    assert 'aria-label="Restaurar tamanho padrão da fonte"' in page
    assert 'aria-label="Tema claro ativo. Ativar tema escuro"' in page
    assert 'aria-live="polite"' in page


def test_recursos_de_acessibilidade_sao_servidos(client):
    script = client.get("/static/js/app.js")
    stylesheet = client.get("/static/css/style.css")

    assert script.status_code == 200
    assert 'jay-marques-font-scale' in script.get_data(as_text=True)
    assert 'jay-marques-theme' in script.get_data(as_text=True)
    assert stylesheet.status_code == 200
    assert 'html[data-theme="dark"]' in stylesheet.get_data(as_text=True)
    assert ':focus-visible' in stylesheet.get_data(as_text=True)


def test_logo_oficial_fornecido_e_servido_sem_alteracao(client):
    page = client.get("/").get_data(as_text=True)
    logo = client.get("/static/img/marques-stores-reference.jpeg")

    assert 'alt="Marques Stores"' in page
    assert logo.status_code == 200
    assert logo.mimetype == "image/jpeg"
    assert len(logo.data) == 139085
