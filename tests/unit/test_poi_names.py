"""Tests convention de nommage POI Deployment Tool."""

import pytest

from sdk.poi_names import is_valid_deployment_poi_name


@pytest.mark.parametrize(
    "name",
    [
        "CNC ROUTEUR",
        "EXTRUSION-SOUFFLAGE",
        "POSTE-REMPLISSAGE-BOUCHONNAGE",
        "GAMME-CONTROLE-QUALITE",
        "IMPRIMANTE 3D",
        "SÉRIGRAPHIE",
        "THERMOFORMAGE",
    ],
)
def test_valid_deployment_poi_names(name: str) -> None:
    assert is_valid_deployment_poi_name(name)


@pytest.mark.parametrize(
    "name",
    [
        "",
        "Routeur CNC",
        "Extraction et soufflage",
        "Station LG-09",
        "LG-10",
        "LG-09",
        "Imprimante DTF C31 XP600",
        "move",
        "nous",
        "point2",
        "thermoformage",
    ],
)
def test_invalid_obsolete_poi_names(name: str) -> None:
    assert not is_valid_deployment_poi_name(name)
