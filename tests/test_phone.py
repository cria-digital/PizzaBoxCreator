from app.utils.phone import normalize_phone


def test_strips_formatting():
    assert normalize_phone("(11) 98888-7777") == "11988887777"


def test_keeps_already_normalized():
    assert normalize_phone("5511988887777") == "5511988887777"


def test_empty_and_none():
    assert normalize_phone("") == ""
    assert normalize_phone(None) == ""


def test_strips_letters_and_symbols():
    assert normalize_phone("tel: 11-98888.7777 (whats)") == "11988887777"
