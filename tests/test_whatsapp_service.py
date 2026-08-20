from app.services.whatsapp_service import _extract_quantity, _is_approval, _match_template


def test_extract_quantity_requires_unit_word():
    assert _extract_quantity("quero 1000 caixas") == 1000
    assert _extract_quantity("500 unidades por favor") == 500
    assert _extract_quantity("300 pecas, tema kraft") == 300


def test_extract_quantity_ignores_unrelated_numbers():
    # a phone number alone must never be mistaken for a quantity
    assert _extract_quantity("(11) 98888-7777") is None
    assert _extract_quantity("sem numero nenhum aqui") is None


def test_is_approval_matches_known_keywords():
    assert _is_approval("aprovado!")
    assert _is_approval("pode produzir, ta show")
    assert _is_approval("confirmo o pedido")


def test_is_approval_rejects_feedback():
    assert not _is_approval("nao gostei da cor")
    assert not _is_approval("quero mudar a frase")


def test_match_template_by_number(db, sample_template):
    matched = _match_template(db, "1")
    assert matched["id"] == sample_template["id"]


def test_match_template_by_name_substring(db, sample_template):
    matched = _match_template(db, "caixa teste")
    assert matched["id"] == sample_template["id"]


def test_match_template_out_of_range_number(db, sample_template):
    assert _match_template(db, "99") is None


def test_match_template_no_match(db, sample_template):
    assert _match_template(db, "modelo que nao existe") is None


def test_match_template_empty_text(db, sample_template):
    assert _match_template(db, None) is None
    assert _match_template(db, "") is None
