"""Tests filtrage arrêts visite guidée selon POI carte."""

from sdk.lab_tour import filter_tour_by_poi, load_lab_tour


def test_filter_tour_removes_obsolete_lg10() -> None:
    tour = load_lab_tour()
    filtered = filter_tour_by_poi(
        tour,
        {"LG-10", "CNC ROUTEUR", "PORTE-LABO", "IMPRIMANTE 3D"},
    )
    names = {s.target_point for s in filtered.stops if s.target_point}
    assert "LG-10" not in names
    assert "CNC ROUTEUR" in names


def test_filter_tour_skips_missing_ros_poi() -> None:
    tour = load_lab_tour()
    filtered = filter_tour_by_poi(tour, {"PORTE-LABO", "CNC ROUTEUR"})
    names = {s.target_point for s in filtered.stops if s.target_point}
    assert names <= {"PORTE-LABO", "CNC ROUTEUR"}
