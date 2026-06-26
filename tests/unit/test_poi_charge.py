"""Tests POI charge / visite."""

from sdk.lab_tour import filter_tour_by_poi, load_lab_tour
from sdk.marker_utils import merge_point_dicts
from sdk.poi_names import is_charge_poi_name, is_visitor_poi


def test_charge_poi_excluded_from_visitor_list() -> None:
    assert is_charge_poi_name("POINT-RECHARGE")
    assert not is_visitor_poi("POINT-RECHARGE")


def test_merge_excludes_charge_from_kiosk() -> None:
    ros = [
        {"name": "PORTE-LABO", "x": 1.0, "y": 2.0, "type": "common"},
        {"name": "POINT-RECHARGE", "x": 0.0, "y": 0.0, "type": "common"},
    ]
    merged = merge_point_dicts([], ros, mark_kiosk={"PORTE-LABO"})
    by_name = {p["name"]: p for p in merged}
    assert by_name["PORTE-LABO"]["kiosk_visible"] is True
    assert by_name["POINT-RECHARGE"]["kiosk_visible"] is False


def test_filter_tour_skips_charge_and_obsolete() -> None:
    tour = load_lab_tour()
    filtered = filter_tour_by_poi(
        tour,
        {"PORTE-LABO", "POINT-RECHARGE", "GAMME-CONTROLE-QUALITE"},
    )
    names = {s.target_point for s in filtered.stops if s.target_point}
    assert "POINT-RECHARGE" not in names
    assert "GAMME-CONTROLE-QUALITE" not in names
