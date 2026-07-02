"""Tests visite guidée — navigation par POI (target_point)."""

from pathlib import Path

from sdk.lab_tour import TourStop, load_lab_tour


def test_lab_tour_stops_use_target_point_not_coordinates() -> None:
    tour = load_lab_tour(Path(__file__).resolve().parents[2] / "data" / "lab_tour.json")
    assert len(tour.stops) == 10
    for stop in tour.stops:
        assert stop.target_point, f"Arrêt {stop.id} sans target_point"
        assert not stop.has_coordinates(), f"Arrêt {stop.id} a encore des coordonnées"
        assert stop.prefers_poi_navigation()


def test_tour_stop_poi_priority() -> None:
    stop = TourStop(
        id="test",
        name_fr="Test",
        name_en="Test",
        equipment_fr="Equipement",
        equipment_en="Equipment",
        speech_fr="",
        speech_en="",
        target_point="CNC ROUTEUR",
        x=1.0,
        y=2.0,
    )
    assert stop.prefers_poi_navigation()
    assert stop.has_coordinates()
