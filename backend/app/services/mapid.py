from typing import Any

import httpx

from app.core.config import settings


class MapidError(RuntimeError):
    """Raised when a layer cannot be retrieved from the MAPID Geoserver."""


def fetch_layer(layer_id: str, timeout: float = 30.0) -> Any:
    """Fetch a single layer from the MAPID Geoserver."""
    if not settings.MAPID_API_KEY or not settings.MAPID_PROJECT_ID:
        raise MapidError("MAPID_API_KEY / MAPID_PROJECT_ID is not set in .env")

    url = f"{settings.MAPID_GEOSERVER_URL}/layers_new/get_layer"
    params = {
        "api_key": settings.MAPID_API_KEY,
        "project_id": settings.MAPID_PROJECT_ID,
        "layer_id": layer_id,
    }

    try:
        response = httpx.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as exc:
        raise MapidError(f"layer {layer_id}: {exc}") from exc


def extract_features(payload: Any) -> list[dict]:
    """
    Locate the list of GeoJSON features inside a response.

    The exact envelope used by the MAPID Geoserver is not confirmed yet, so
    this walks the keys that such APIs commonly wrap their payload in.
    """
    if isinstance(payload, dict):
        if payload.get("type") == "FeatureCollection":
            return payload.get("features") or []
        for key in ("geojson", "data", "layer", "result", "features"):
            if key in payload:
                found = extract_features(payload[key])
                if found:
                    return found

    if isinstance(payload, list) and payload and isinstance(payload[0], dict):
        if payload[0].get("type") == "Feature":
            return payload

    return []
