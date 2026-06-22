from sdk.models import MapData, MapMetadata


def parse_occupancy_grid(msg: dict) -> MapData | None:
    """Parse un message ROS OccupancyGrid ou format custom similaire."""
    info = msg.get("info") or msg.get("metadata") or {}
    raw_data = msg.get("data")

    if raw_data is None:
        return None

    width = int(info.get("width") or msg.get("width") or 0)
    height = int(info.get("height") or msg.get("height") or 0)
    resolution = float(info.get("resolution") or msg.get("resolution") or 0.05)

    origin = info.get("origin") or {}
    position = origin.get("position") or origin
    origin_x = float(position.get("x") or msg.get("origin_x") or 0.0)
    origin_y = float(position.get("y") or msg.get("origin_y") or 0.0)

    if width <= 0 or height <= 0:
        if len(raw_data) > 0:
            side = int(len(raw_data) ** 0.5)
            width = height = side
        else:
            return None

    data = [int(v) for v in raw_data]
    area = width * resolution * height * resolution

    return MapData(
        metadata=MapMetadata(
            name=str(msg.get("name") or msg.get("map_name") or "carte"),
            floor=str(msg.get("floor") or msg.get("floor_name") or "0"),
            width=width,
            height=height,
            resolution=resolution,
            origin_x=origin_x,
            origin_y=origin_y,
            area_sqm=round(area, 2),
        ),
        data=data,
    )


OCCUPANCY_OBSTACLE_THRESHOLD = 65


def get_cell_value(map_data: MapData | None, x: float, y: float) -> int | None:
    """Valeur de cellule (-1 inconnu, 0 libre, 100 occupé), ou None hors carte."""
    if not map_data:
        return None
    meta = map_data.metadata
    gx = int((x - meta.origin_x) / meta.resolution)
    gy = int((y - meta.origin_y) / meta.resolution)
    if gx < 0 or gy < 0 or gx >= meta.width or gy >= meta.height:
        return None
    return map_data.data[gy * meta.width + gx]


def is_coordinate_navigable(
    map_data: MapData | None,
    x: float,
    y: float,
    threshold: int = OCCUPANCY_OBSTACLE_THRESHOLD,
) -> bool:
    cell = get_cell_value(map_data, x, y)
    if cell is None:
        return False
    return 0 <= cell < threshold


def parse_map_metadata(msg: dict) -> MapMetadata | None:
    if not msg:
        return None

    width = int(msg.get("width") or 0)
    height = int(msg.get("height") or 0)
    if width <= 0 or height <= 0:
        return None

    resolution = float(msg.get("resolution") or 0.05)
    origin = msg.get("origin") or {}
    position = origin.get("position") if isinstance(origin, dict) else {}
    if not position:
        position = origin if isinstance(origin, dict) else {}

    origin_x = float((position or {}).get("x") or 0.0)
    origin_y = float((position or {}).get("y") or 0.0)
    area = width * resolution * height * resolution

    return MapMetadata(
        name=str(msg.get("map_load_time") or msg.get("name") or "carte"),
        floor="0",
        width=width,
        height=height,
        resolution=resolution,
        origin_x=origin_x,
        origin_y=origin_y,
        area_sqm=round(area, 2),
    )
