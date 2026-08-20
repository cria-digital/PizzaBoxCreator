from app.ai.agent import parse_message_offline, parse_message_to_dict
from app.models.commands import TemaFundo


def test_extracts_phone():
    cmd = parse_message_offline("meu telefone e (11) 98888-7777")
    assert cmd.telefone == "(11) 98888-7777"


def test_extracts_instagram():
    cmd = parse_message_offline("segue a gente @pizzaria_demo")
    assert cmd.instagram == "@pizzaria_demo"


def test_extracts_tema_premium():
    cmd = parse_message_offline("quero o fundo preto premium")
    assert cmd.tema_fundo == TemaFundo.premium


def test_extracts_tema_tradicional():
    cmd = parse_message_offline("prefiro o kraft tradicional")
    assert cmd.tema_fundo == TemaFundo.tradicional


def test_extracts_selo_entrega():
    cmd = parse_message_offline("adiciona o selo de entrega rapida")
    assert cmd.adicionar_selo_entrega is True


def test_extracts_forno_lenha():
    cmd = parse_message_offline("quero a ilustracao do forno a lenha, bem artesanal")
    assert cmd.adicionar_forno_lenha is True


def test_extracts_frase_with_quotes():
    cmd = parse_message_offline('escrever: "Bom Apetite!"')
    assert cmd.frase == "Bom Apetite!"


def test_empty_message_returns_empty_command():
    cmd = parse_message_offline("oi, tudo bem?")
    assert cmd.telefone is None
    assert cmd.instagram is None
    assert cmd.tema_fundo is None
    assert cmd.adicionar_selo_entrega is False


def test_parse_message_to_dict_uses_offline_without_api_key(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "anthropic_api_key", "")
    result = parse_message_to_dict("meu telefone e (11) 98888-7777")
    assert result["telefone"] == "(11) 98888-7777"
    assert "adicionar_selo_entrega" not in result  # False values are dropped
