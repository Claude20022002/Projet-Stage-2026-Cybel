import asyncio

import pytest

from sdk.lab_tour import LabTour, TourEngine, TourStop


@pytest.mark.asyncio
async def test_tour_sequence_navigate_before_speech():
  """À chaque arrêt : navigation d'abord, puis discours."""
  events: list[str] = []

  tour = LabTour(
      id="t",
      title_fr="T",
      title_en="T",
      subtitle_fr="",
      subtitle_en="",
      intro_speech_fr="",
      intro_speech_en="",
      outro_speech_fr="",
      outro_speech_en="",
      stops=[
          TourStop(
              id="a",
              name_fr="A",
              name_en="A",
              equipment_fr="Machine A",
              equipment_en="A",
              speech_fr="Présentation A",
              speech_en="A",
              x=1.0,
              y=2.0,
              theta=0.0,
              approach_speech_fr="Nous voici à A",
              dwell_seconds=0.1,
          ),
      ],
  )

  async def speak(text: str) -> None:
      events.append(f"speak:{text}")

  async def navigate(stop: TourStop) -> None:
      events.append(f"nav:{stop.id}")
      await asyncio.sleep(0.05)

  engine = TourEngine(tour, speak, navigate, lambda: asyncio.sleep(0))
  await engine.start("fr")
  await asyncio.sleep(0.5)

  assert "nav:a" in events
  assert "speak:Nous voici à A" in events
  assert "speak:Présentation A" in events
  assert events.index("nav:a") < events.index("speak:Nous voici à A")
  assert events.index("speak:Nous voici à A") < events.index("speak:Présentation A")
