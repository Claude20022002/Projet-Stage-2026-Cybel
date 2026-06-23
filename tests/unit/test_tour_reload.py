import pytest

from backend.services.tour_service import TourService


def test_tour_start_reloads_engine_from_disk(tmp_path, monkeypatch):
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
    "equipment_fr": "Machine A",
    "speech_fr": "Texte",
    "x": 1.0,
    "y": 2.0,
    "theta": 0.0
  }]
}""",
        encoding="utf-8",
    )

    service = TourService()
    service._tour_path = tour_path
    engine1 = service._ensure_engine()
    assert engine1.tour.stops[0].equipment_fr == "Machine A"

    tour_path.write_text(
        tour_path.read_text(encoding="utf-8").replace("Machine A", "Machine B"),
        encoding="utf-8",
    )
    service.reset_engine()
    engine2 = service._ensure_engine()
    assert engine2.tour.stops[0].equipment_fr == "Machine B"
