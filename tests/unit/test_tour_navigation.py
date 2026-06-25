from sdk.tour_navigation import (
    assess_tour_readiness,
    navigation_wait_failure_message,
    normalize_localization_percent,
    parse_localization_percent,
)


def test_normalize_localization_fraction():
    assert normalize_localization_percent(0.72) == 72.0
    assert normalize_localization_percent(85) == 85.0


def test_parse_localization_from_confidence_topic():
    loc = parse_localization_percent({}, {"data": 0.65})
    assert loc == 65.0


def test_parse_localization_from_matching_degree():
    loc = parse_localization_percent({"matching_degree": 72.5}, None)
    assert loc == 72.5


def test_assess_tour_readiness_blocks_unknown_localization():
    ok, msg = assess_tour_readiness(601, None, require_known_localization=True)
    assert not ok
    assert "inconnue" in msg.lower()


def test_assess_tour_readiness_blocks_604():
    ok, msg = assess_tour_readiness(604, 80.0)
    assert not ok
    assert "604" in msg or "Échec" in msg


def test_assess_tour_readiness_blocks_low_localization():
    ok, msg = assess_tour_readiness(601, 45.0, min_localization=60.0)
    assert not ok
    assert "45" in msg


def test_assess_tour_readiness_ok():
    ok, msg = assess_tour_readiness(601, 75.0, min_localization=60.0)
    assert ok
    assert msg == ""


def test_navigation_wait_failure_never_started():
    msg = navigation_wait_failure_message(
        601,
        destination="Routeur CNC",
        never_started=True,
        distance_to_target_m=3.3,
    )
    assert "n'a pas démarré" in msg
    assert "3.30" in msg
    assert "604" not in msg.split("obstacle")[0]
