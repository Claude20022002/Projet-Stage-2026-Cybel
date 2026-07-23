"""Tests réordonnancement plus-proche-voisin de la visite guidée (demande
utilisateur : visite ~11-14 min jugée trop longue — réduire la distance
totale parcourue en visitant les arrêts par proximité plutôt que dans
l'ordre fixe du fichier)."""

from sdk.lab_tour import (
    LabTour,
    TourStop,
    load_lab_tour,
    reorder_stops_nearest_first,
)


def _stop(stop_id: str, target_point: str | None = None, x: float | None = None, y: float | None = None) -> TourStop:
    return TourStop(
        id=stop_id,
        name_fr=stop_id,
        name_en=stop_id,
        equipment_fr=stop_id,
        equipment_en=stop_id,
        speech_fr="",
        speech_en="",
        target_point=target_point,
        x=x,
        y=y,
    )


def _tour(stops: list[TourStop]) -> LabTour:
    return LabTour(
        id="test",
        title_fr="",
        title_en="",
        subtitle_fr="",
        subtitle_en="",
        intro_speech_fr="",
        intro_speech_en="",
        outro_speech_fr="",
        outro_speech_en="",
        stops=stops,
    )


def test_reorder_visits_nearest_poi_first() -> None:
    tour = _tour(
        [
            _stop("far", target_point="FAR"),
            _stop("near", target_point="NEAR"),
            _stop("mid", target_point="MID"),
        ]
    )
    point_coords = {"FAR": (10.0, 0.0), "NEAR": (1.0, 0.0), "MID": (5.0, 0.0)}
    reordered = reorder_stops_nearest_first(tour, start_xy=(0.0, 0.0), point_coords=point_coords)
    assert [s.id for s in reordered.stops] == ["near", "mid", "far"]


def test_reorder_chains_from_last_visited_position() -> None:
    # Départ proche de A ; une fois à A, C est plus proche que B (piège pour
    # un tri naïf par distance-au-point-de-départ seul, pas plus-proche-voisin réel).
    tour = _tour(
        [
            _stop("a", target_point="A"),
            _stop("b", target_point="B"),
            _stop("c", target_point="C"),
        ]
    )
    point_coords = {"A": (1.0, 0.0), "B": (10.0, 0.0), "C": (2.0, 0.0)}
    reordered = reorder_stops_nearest_first(tour, start_xy=(0.0, 0.0), point_coords=point_coords)
    assert [s.id for s in reordered.stops] == ["a", "c", "b"]


def test_reorder_uses_direct_coordinates_when_no_target_point() -> None:
    tour = _tour([_stop("far", x=10.0, y=0.0), _stop("near", x=1.0, y=0.0)])
    reordered = reorder_stops_nearest_first(tour, start_xy=(0.0, 0.0), point_coords={})
    assert [s.id for s in reordered.stops] == ["near", "far"]


def test_reorder_appends_unresolvable_stops_at_end_in_original_order() -> None:
    tour = _tour(
        [
            _stop("unresolvable_1", target_point="UNKNOWN_1"),
            _stop("near", target_point="NEAR"),
            _stop("unresolvable_2", target_point="UNKNOWN_2"),
        ]
    )
    point_coords = {"NEAR": (1.0, 0.0)}
    reordered = reorder_stops_nearest_first(tour, start_xy=(0.0, 0.0), point_coords=point_coords)
    assert [s.id for s in reordered.stops] == ["near", "unresolvable_1", "unresolvable_2"]


def test_reorder_preserves_stop_count_and_identity_on_real_tour() -> None:
    tour = load_lab_tour()
    point_coords = {
        s.target_point: (0.0, float(i))
        for i, s in enumerate(tour.stops)
        if s.target_point
    }
    reordered = reorder_stops_nearest_first(tour, start_xy=(0.0, -1.0), point_coords=point_coords)
    assert len(reordered.stops) == len(tour.stops)
    assert {s.id for s in reordered.stops} == {s.id for s in tour.stops}
