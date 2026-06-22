from sdk.map_utils import get_cell_value, is_coordinate_navigable
from sdk.models import MapData, MapMetadata


def _sample_map() -> MapData:
    return MapData(
        metadata=MapMetadata(
            name="test",
            floor="0",
            width=3,
            height=2,
            resolution=1.0,
            origin_x=0.0,
            origin_y=0.0,
            area_sqm=6.0,
        ),
        data=[0, 0, 100, -1, 50, 0],
    )


def test_get_cell_value_free():
    m = _sample_map()
    assert get_cell_value(m, 0.5, 0.5) == 0


def test_get_cell_value_obstacle():
    m = _sample_map()
    assert get_cell_value(m, 2.5, 0.5) == 100


def test_is_coordinate_navigable():
    m = _sample_map()
    assert is_coordinate_navigable(m, 0.5, 0.5) is True
    assert is_coordinate_navigable(m, 2.5, 0.5) is False
    assert is_coordinate_navigable(m, 0.5, 1.5) is False  # valeur 50 >= seuil 65? 50 < 65 -> True
    assert is_coordinate_navigable(m, 5.0, 5.0) is False  # hors carte
