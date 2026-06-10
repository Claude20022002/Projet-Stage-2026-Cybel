import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import APIRouter, HTTPException

from sdk.models import MapData, MapMetadata
from services.robot_service import robot_service

router = APIRouter(prefix="/api/map", tags=["map"])


@router.get("/current", response_model=MapData)
async def get_current_map() -> MapData:
    map_data = robot_service.get_map()
    if not map_data:
        raise HTTPException(status_code=404, detail="Carte non disponible")
    return map_data


@router.get("/metadata", response_model=MapMetadata)
async def get_map_metadata() -> MapMetadata:
    map_data = robot_service.get_map()
    if not map_data:
        raise HTTPException(status_code=404, detail="Métadonnées carte non disponibles")
    return map_data.metadata
