from pathlib import Path

from sdk.lab_tour import TourEngine, load_lab_tour


def test_tour_engine_reflects_reloaded_json(tmp_path: Path):
    tour_path = tmp_path / "lab_tour.json"
    tour_path.write_text(
        """{
  "id": "t1",
  "title_fr": "T",
  "title_en": "T",
  "subtitle_fr": "",
  "subtitle_en": "",
  "intro_speech_fr": "",
  "intro_speech_en": "",
  "outro_speech_fr": "",
  "outro_speech_en": "",
  "stops": [{
    "id": "a",
    "name_fr": "A",
    "equipment_fr": "Machine A",
    "speech_fr": "Texte",
    "x": 1.0,
    "y": 2.0,
    "theta": 0.0
  }]
}""",
        encoding="utf-8",
    )

    tour_a = load_lab_tour(tour_path)
    assert tour_a.stops[0].equipment_fr == "Machine A"

    tour_path.write_text(
        tour_path.read_text(encoding="utf-8").replace("Machine A", "Machine B"),
        encoding="utf-8",
    )
    tour_b = load_lab_tour(tour_path)
    assert tour_b.stops[0].equipment_fr == "Machine B"

    async def noop(_: str) -> None:
        return None

    async def nav(_stop) -> None:
        return None

    engine = TourEngine(tour_b, noop, nav, noop)
    assert engine.tour.stops[0].equipment_fr == "Machine B"
