from models import MapData, MapMetadata


def generate_mock_map() -> MapData:
    width, height = 260, 200
    resolution = 0.05
    origin_x, origin_y = -5.0, -4.0

    data = [0] * (width * height)

    def set_cell(gx: int, gy: int, value: int = 100) -> None:
        if 0 <= gx < width and 0 <= gy < height:
            data[gy * width + gx] = value

    def fill_rect(x1: int, y1: int, x2: int, y2: int, value: int = 100) -> None:
        for gy in range(y1, y2 + 1):
            for gx in range(x1, x2 + 1):
                set_cell(gx, gy, value)

    # Murs extérieurs
    fill_rect(0, 0, width - 1, 2)
    fill_rect(0, height - 3, width - 1, height - 1)
    fill_rect(0, 0, 2, height - 1)
    fill_rect(width - 3, 0, width - 1, height - 1)

    # Cloisons intérieures
    fill_rect(80, 40, 82, 150)
    fill_rect(160, 20, 162, 120)
    fill_rect(40, 100, 200, 102)

    # Obstacle central
    fill_rect(110, 60, 140, 85)

    # Zone ouverte accueil
    for gy in range(30, 70):
        for gx in range(30, 70):
            set_cell(gx, gy, 0)

    area = (width * resolution) * (height * resolution)

    return MapData(
        metadata=MapMetadata(
            name="robotics",
            floor="0",
            width=width,
            height=height,
            resolution=resolution,
            origin_x=origin_x,
            origin_y=origin_y,
            area_sqm=round(area, 2),
        ),
        data=data,
    )
