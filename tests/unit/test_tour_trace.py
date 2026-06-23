from sdk.tour_trace import TourSessionLogger, stop_target_dict


def test_stop_target_dict_coordinates():
    stop = {
        "id": "cnc",
        "equipment_fr": "Routeur CNC",
        "x": -8.38,
        "y": 1.45,
        "theta": 0.88,
    }
    target = stop_target_dict(stop)
    assert target["target_type"] == "coordinates"
    assert target["x"] == -8.38


def test_tour_logger_writes_entries(tmp_path):
    logger = TourSessionLogger(log_dir=tmp_path, tour_id="test")
    logger.tour_start("fr", [{"id": "a", "equipment_fr": "A", "x": 1, "y": 2}])
    logger.nav_command(
        {"id": "a", "equipment_fr": "A", "x": 1, "y": 2},
        index=0,
        robot={"x": 0, "y": 0, "theta": 0},
        nav_status=601,
        nav_status_label="Prêt",
    )
    payload = logger.status_payload()
    assert payload["session_id"]
    assert len(payload["entries"]) == 2
    assert logger.log_file is not None
    assert logger.log_file.is_file()
