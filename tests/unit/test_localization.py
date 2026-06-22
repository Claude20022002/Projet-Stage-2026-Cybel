from sdk.real_robot import normalize_localization_percent, localization_label


def test_normalize_fraction():
    assert normalize_localization_percent(0.72) == 72.0


def test_normalize_percent():
    assert normalize_localization_percent(57.2) == 57.2


def test_localization_labels():
    assert localization_label(45) == "Faible"
    assert localization_label(65) == "Moyenne"
    assert localization_label(85) == "Bonne"
