from typing import Any

import httpx

from app.core.config import settings

# Geoserver MAPID memotong tiap balasan di 200 fitur dan tidak memberi tahu:
# tidak ada penanda total, tidak ada penanda sisa halaman. Layer 1.700 titik
# tetap terlihat "berhasil" dengan 200 baris. Satu-satunya cara menarik utuh
# adalah memanggil ulang dengan `skip` sampai halamannya tidak penuh lagi.
PAGE_SIZE = 200

# Pagar pengaman kalau suatu saat server berhenti menghormati `skip`. Tanpa ini
# layer yang selalu mengembalikan halaman penuh bikin loopnya jalan selamanya.
MAX_PAGES = 250


class MapidError(RuntimeError):
    """Raised when a layer cannot be retrieved from the MAPID Geoserver."""


def _require_credentials() -> None:
    if not settings.MAPID_API_KEY or not settings.MAPID_PROJECT_ID:
        raise MapidError("MAPID_API_KEY / MAPID_PROJECT_ID is not set in .env")


def _feature_key(feature: dict) -> str:
    """Penanda unik satu fitur, dipakai buat mendeteksi halaman yang terulang."""
    marker = feature.get("id")
    if marker is not None:
        return str(marker)

    props = feature.get("properties") or {}
    name = props.get("NAMA") or props.get("name") or ""
    return f"{name}|{feature.get('geometry')}"


def _fetch_page(layer_id: str, skip: int, timeout: float) -> Any:
    url = f"{settings.MAPID_GEOSERVER_URL}/layers_new/get_layer"
    params = {
        "api_key": settings.MAPID_API_KEY,
        "project_id": settings.MAPID_PROJECT_ID,
        "layer_id": layer_id,
        "skip": skip,
    }

    try:
        response = httpx.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as exc:
        raise MapidError(f"layer {layer_id}: {exc}") from exc


def fetch_layer(layer_id: str, timeout: float = 60.0) -> Any:
    """Fetch one layer in full, following pagination until the last page."""
    _require_credentials()

    envelope: dict[str, Any] = {}
    features: list[dict] = []
    seen: set[str] = set()

    for page in range(MAX_PAGES):
        payload = _fetch_page(layer_id, page * PAGE_SIZE, timeout)
        batch = extract_features(payload)

        if page == 0 and isinstance(payload, dict):
            envelope = payload

        fresh = [f for f in batch if _feature_key(f) not in seen]
        seen.update(_feature_key(f) for f in batch)
        features.extend(fresh)

        # Halaman tidak penuh berarti sudah habis. `fresh` kosong berarti server
        # mengabaikan `skip` dan menyodorkan halaman yang sama — berhenti juga,
        # daripada menumpuk permintaan yang tidak menambah apa-apa.
        if len(batch) < PAGE_SIZE or not fresh:
            break
    else:
        raise MapidError(
            f"layer {layer_id}: masih penuh setelah {MAX_PAGES} halaman, paginasi dihentikan"
        )

    if envelope:
        return {**envelope, "features": features}

    return features


def fetch_layer_list(timeout: float = 60.0) -> list[dict]:
    """List every layer in the project, straight from the Geoserver.

    Undocumented but stable: it is what the GEO MAPID dashboard itself calls.
    Saves hunting for layer ids by hand.
    """
    _require_credentials()

    url = f"{settings.MAPID_GEOSERVER_URL}/layers_new/get_layer_list"
    params = {
        "api_key": settings.MAPID_API_KEY,
        "project_id": settings.MAPID_PROJECT_ID,
    }

    try:
        response = httpx.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPError as exc:
        raise MapidError(f"daftar layer: {exc}") from exc

    if isinstance(payload, list):
        return payload

    if isinstance(payload, dict):
        for key in ("layers", "data", "result"):
            found = payload.get(key)
            if isinstance(found, list):
                return found

    raise MapidError("bentuk balasan daftar layer tidak dikenali")


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
