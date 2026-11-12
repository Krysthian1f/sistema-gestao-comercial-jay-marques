from pathlib import Path

from app import _load_or_create_secret_key


def test_chave_de_ambiente_tem_precedencia_e_nao_cria_arquivo(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setenv("SECRET_KEY", "chave-configurada-no-ambiente")

    key = _load_or_create_secret_key(tmp_path)

    assert key == "chave-configurada-no-ambiente"
    assert not (tmp_path / ".secret_key").exists()


def test_chave_local_e_criada_e_reutilizada(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setattr("app.secrets.token_urlsafe", lambda _length: "chave-gerada-para-teste")

    first_key = _load_or_create_secret_key(tmp_path)
    second_key = _load_or_create_secret_key(tmp_path)

    assert first_key == "chave-gerada-para-teste"
    assert second_key == first_key
    assert (tmp_path / ".secret_key").read_text(encoding="utf-8") == first_key


def test_colisao_na_criacao_reutiliza_chave_existente_sem_sobrescrever(
    tmp_path: Path, monkeypatch
):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setattr("app.secrets.token_urlsafe", lambda _length: "chave-deste-processo")

    key_path = tmp_path / ".secret_key"
    original_open = Path.open

    def create_key_before_exclusive_open(path, mode="r", *args, **kwargs):
        if path == key_path and mode == "x":
            with original_open(path, "w", encoding="utf-8") as key_file:
                key_file.write("chave-criada-por-outro-processo")
            raise FileExistsError
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", create_key_before_exclusive_open)

    key = _load_or_create_secret_key(tmp_path)

    assert key == "chave-criada-por-outro-processo"
    assert key_path.read_text(encoding="utf-8") == key
