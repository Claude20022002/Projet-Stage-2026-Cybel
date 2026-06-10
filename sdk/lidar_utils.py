import math

from sdk.models import LidarPoint, Pose


def parse_laser_scan(msg: dict, robot_pose: Pose | None = None) -> list[LidarPoint]:
    """Convertit un message sensor_msgs/LaserScan en points monde."""
    ranges = msg.get("ranges") or []
    if not ranges:
        return []

    angle_min = float(msg.get("angle_min", -math.pi))
    angle_increment = float(msg.get("angle_increment", 0.0))
    range_min = float(msg.get("range_min", 0.1))
    range_max = float(msg.get("range_max", 30.0))

    pose = robot_pose or Pose()
    points: list[LidarPoint] = []

    for i, raw_range in enumerate(ranges):
        if raw_range is None:
            continue
        dist = float(raw_range)
        if dist < range_min or dist > range_max or math.isinf(dist) or math.isnan(dist):
            continue

        angle = angle_min + i * angle_increment
        world_angle = pose.theta + angle
        x = pose.x + dist * math.cos(world_angle)
        y = pose.y + dist * math.sin(world_angle)
        points.append(LidarPoint(x=x, y=y, distance=dist))

    return points


def mock_lidar_points(pose: Pose, count: int = 60) -> list[LidarPoint]:
    """Simule un arc LiDAR devant le robot."""
    points: list[LidarPoint] = []
    for i in range(count):
        angle = pose.theta - 0.8 + (1.6 * i / max(count - 1, 1))
        dist = 1.2 + 0.4 * math.sin(i * 0.3)
        x = pose.x + dist * math.cos(angle)
        y = pose.y + dist * math.sin(angle)
        points.append(LidarPoint(x=x, y=y, distance=dist))
    return points
