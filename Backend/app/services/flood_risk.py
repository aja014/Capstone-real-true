"""Shared GIS flood-risk lookup (Objective 2.1, extended with storm surge).

Given a free-text address, geocode it via OpenStreetMap Nominatim, then run a
point-in-polygon check against TWO hazard datasets:
  - Bulacan 100-year RIVER FLOOD hazard shapefile
    (gis_data/flood_hazard/bulacan_100yr/extracted/Bulacan_Flood_100year.shp —
    Var 1=Low, 2=Medium, 3=High).
  - Bulacan STORM SURGE SSA3 hazard shapefile
    (gis_data/storm_surge/bulacan/extracted/SSA3/Bulacan_StormSurge_SSA3.shp —
    HAZ 1=Low, 2=Medium, 3=High). SSA3 (the 3rd of 4 increasingly-severe
    advisory-level shapefiles) was chosen as the single storm-surge scenario
    to combine in, rather than checking all 4 or making it configurable —
    a fixed middle-severity scenario keeps the combined result meaningful
    without turning this into a 4-scenario feature choice this capstone's
    scope doesn't call for.

The two results are combined into a single "headline" result (whichever
hazard is more severe wins — Low < Medium < High, with "outside every zone"
counting as the lowest, safer-than-Low case) alongside the two individual
breakdowns, so a point missed by the flood-only check (e.g. Bulacan's
coastal barangays) still gets a real risk result from storm surge instead of
looking flood-free.

Both checks apply a BOUNDARY_BUFFER_METERS (50m) buffer: a point within 50
real meters of a zone's edge counts as inside it, even if technically just
outside. Real Bulacan addresses were found to routinely geocode to within a
few meters of a hazard polygon boundary (river-adjacent town centers sit
right at the edge of their floodplain by nature), so a hard yes/no
point-in-polygon test was flipping known-risky addresses to "no risk" on
geocoding/polygon-precision noise alone. 50m was chosen from real
measurements, not a guess — see CLAUDE.md "Hazard Boundary Buffer" for the
full investigation and the specific distances behind it.

Used by both Fire/Property Survey and Motor Quotation creation (manual +
bulk import + needs-review resolve) so the logic lives in exactly one place.

This is a best-effort enrichment step, never a hard dependency: every failure
mode (empty address, geocode miss, network error, unreadable shapefile, an
invalid/self-intersecting polygon tripping up a contains() check) is caught
here and turned into "no result" rather than an exception, so a caller never
needs its own try/except around lookup_flood_risk(). The two hazard checks
fail independently of each other — if one shapefile can't be loaded, the
other's result (and the combined headline) is unaffected.

Reading the shapefiles: each holds only 3 features (one dissolved multi-
polygon per hazard class), but each feature is huge and formally invalid per
GEOS (self-intersections typical of dissolved/raster-derived hazard
polygons). geopandas/fiona aren't installed (and don't have wheels for this
project's Python 3.14 venv) and pyshp's pure-Python per-feature parsing is
far too slow at this size (a from-scratch load in pyshp didn't finish in
several minutes on the flood file). pyogrio's GDAL-backed reader loads all 3
features in ~2.5s. Fixing validity with shapely.make_valid() on geometries
this large took 4+ minutes and was killed, twice, so it's deliberately
skipped: contains() checks were verified against known points spanning all
hazard classes plus points outside them (see conversation record) and
produced correct, sub-second results despite is_valid == False — a
per-geometry try/except below is the safety net for the rare case a specific
point does trip GEOS on the raw geometry.
"""

import threading
import time
import math
import re
from pathlib import Path
from typing import Optional

import numpy as np
import shapely
import requests
from shapely import Point, from_wkb, prepare
from sqlalchemy import text

from app.database import engine

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# Nominatim usage policy asks for an identifying User-Agent and no more than
# 1 request/second — see https://operations.osmfoundation.org/policies/nominatim/
USER_AGENT = "MaagapCapstoneFloodRiskLookup/1.0 (student capstone project, non-commercial)"
MIN_REQUEST_INTERVAL_SECONDS = 1.0

_GIS_DATA_ROOT = Path(__file__).resolve().parents[3] / "gis_data"

RIVER_FLOOD_SHAPEFILE_PATH = (
    _GIS_DATA_ROOT / "flood_hazard" / "bulacan_100yr" / "extracted" / "Bulacan_Flood_100year.shp"
)
RIVER_FLOOD_FIELD_NAME = "Var"

STORM_SURGE_SHAPEFILE_PATH = (
    _GIS_DATA_ROOT / "storm_surge" / "bulacan" / "extracted" / "SSA3" / "Bulacan_StormSurge_SSA3.shp"
)
STORM_SURGE_FIELD_NAME = "HAZ"

# Both datasets use the same 1/2/3 = Low/Medium/High convention.
_CATEGORY_BY_VALUE = {1: "Low", 2: "Medium", 3: "High"}
_SEVERITY = {None: 0, "Low": 1, "Medium": 2, "High": 3}

# Local equirectangular projection, valid for Bulacan's narrow latitude band
# (~14.7-15.3N) -- accurate to well under 1% at the tens-of-meters scale we
# need here. No pyproj in this project's venv, so zone geometries and query
# points are projected into real meters using a fixed reference latitude
# instead, purely so BOUNDARY_BUFFER_METERS below means actual meters.
_PROJECTION_REF_LAT = 14.8
_METERS_PER_DEGREE_LAT = 111_320.0
_METERS_PER_DEGREE_LON = 111_320.0 * math.cos(math.radians(_PROJECTION_REF_LAT))

# A point within this many real meters of a hazard zone's edge (even if
# technically just outside it) counts as inside that zone. Addresses this
# session's finding: real Bulacan addresses routinely geocode to within a
# few meters of a zone boundary (e.g. Calumpit's Iba/Gatbuca barangays
# needed 25.93m to close, the largest of 6 documented near-misses), while
# every confirmed-safe point tested was >=900m away (Niugan, Angat) -- a
# ~35x margin, so 50m closes every known near-miss without reaching into
# genuinely safe territory. See CLAUDE.md "Hazard Boundary Buffer" for the
# full investigation. Applied uniformly to both datasets, no per-address
# exceptions.
BOUNDARY_BUFFER_METERS = 50.0

_rate_limit_lock = threading.Lock()
_last_request_time = 0.0

_zones_lock = threading.Lock()
_zones_cache: dict[Path, list] = {}  # path -> list[(value: int, prepared shapely geometry, in local meters)]


def _project_coords_to_meters(coords):
    """Vectorized (x=lon, y=lat) degrees -> local meters, for shapely.transform()."""
    coords = np.asarray(coords)
    out = coords.copy()
    out[:, 0] = coords[:, 0] * _METERS_PER_DEGREE_LON
    out[:, 1] = coords[:, 1] * _METERS_PER_DEGREE_LAT
    return out


def _point_to_meters(lat: float, lng: float) -> Point:
    return Point(lng * _METERS_PER_DEGREE_LON, lat * _METERS_PER_DEGREE_LAT)


def _throttle():
    """Blocks (if needed) so calls to Nominatim stay at >=1s apart, process-wide."""
    global _last_request_time
    with _rate_limit_lock:
        elapsed = time.monotonic() - _last_request_time
        if elapsed < MIN_REQUEST_INTERVAL_SECONDS:
            time.sleep(MIN_REQUEST_INTERVAL_SECONDS - elapsed)
        _last_request_time = time.monotonic()


def _geocode_remote(address: str) -> tuple[str, Optional[tuple[float, float]]]:
    """One Nominatim request. Returns ("found", (lat, lng)), ("not_found", None) for a
    definite empty answer, or ("error", None) for anything else (network error,
    timeout, non-200, bad JSON) -- only the first two are ever cached. Never raises."""
    _throttle()
    try:
        response = requests.get(
            NOMINATIM_URL,
            params={"q": address, "format": "json", "limit": 1, "countrycodes": "ph"},
            headers={"User-Agent": USER_AGENT},
            timeout=10,
        )
        response.raise_for_status()
        results = response.json()
        if not results:
            return "not_found", None
        return "found", (float(results[0]["lat"]), float(results[0]["lon"]))
    except Exception:
        return "error", None


def _normalize_address(address: str) -> str:
    # Conservative on purpose: case and whitespace only, so two genuinely different
    # addresses never share a cached result.
    return re.sub(r"\s+", " ", address.strip().lower())


def _cache_get(key: str):
    """(status, coords) from geocode_cache, or None on a miss or any DB problem."""
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT status, latitude, longitude FROM geocode_cache WHERE normalized_address = :k"),
                {"k": key},
            ).first()
    except Exception:
        return None
    if row is None:
        return None
    if row.status == "found" and row.latitude is not None and row.longitude is not None:
        return "found", (float(row.latitude), float(row.longitude))
    if row.status == "not_found":
        return "not_found", None
    return None


def _cache_put(key: str, status: str, coords) -> None:
    """Own short transaction, independent of the caller's row transaction. Never raises."""
    if len(key) > 255:
        return
    lat, lng = coords if coords else (None, None)
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO geocode_cache (normalized_address, latitude, longitude, status) "
                    "VALUES (:k, :lat, :lng, :s) "
                    "ON DUPLICATE KEY UPDATE normalized_address = normalized_address"
                ),
                {"k": key, "lat": lat, "lng": lng, "s": status},
            )
    except Exception:
        pass


def _geocode(address: str) -> Optional[tuple[float, float]]:
    """Returns (lat, lng) for `address`, or None on any miss/error. Never raises.
    Checks geocode_cache first -- a hit skips both the network request and the 1s
    throttle. Caches found results and definite "no result" answers only; errors
    and timeouts are never cached, so they stay retriable."""
    key = _normalize_address(address)
    cached = _cache_get(key)
    if cached is not None:
        return cached[1]
    status, coords = _geocode_remote(address)
    if status in ("found", "not_found"):
        _cache_put(key, status, coords)
    return coords


def _load_zones(path: Path, field_name: str) -> list:
    """Loads + prepares a hazard shapefile's geometries once per process, then caches them.

    Cached independently per shapefile path so a failure loading one hazard
    dataset (e.g. storm surge) never affects an already-cached other one
    (e.g. river flood).
    """
    with _zones_lock:
        if path in _zones_cache:
            return _zones_cache[path]
        try:
            from pyogrio.raw import read as read_shapefile

            meta, _index, geometry, field_data = read_shapefile(str(path), read_geometry=True)
            value_column = list(meta["fields"]).index(field_name)
            values = field_data[value_column]
            geoms = from_wkb(geometry)

            zones = []
            for value, geom in zip(values, geoms):
                geom_m = shapely.transform(geom, _project_coords_to_meters)
                prepare(geom_m)  # builds an internal index for fast repeated contains() calls
                zones.append((int(value), geom_m))
            _zones_cache[path] = zones
        except Exception:
            _zones_cache[path] = []  # fail soft — treat as "hazard data unavailable"
        return _zones_cache[path]


def _classify(lat: float, lng: float, zones: list) -> Optional[str]:
    """Point-in-polygon (+ a BOUNDARY_BUFFER_METERS boundary buffer) against a
    set of hazard zones. Worst case wins on overlap.

    Returns the category string ("Low"/"Medium"/"High"), or None if the point
    falls outside every zone by more than BOUNDARY_BUFFER_METERS (or the zone
    data is unavailable).
    """
    point = _point_to_meters(lat, lng)
    best_value = None
    for value, geom in zones:
        try:
            hit = geom.contains(point) or geom.distance(point) <= BOUNDARY_BUFFER_METERS
        except Exception:
            hit = False
        if hit and (best_value is None or value > best_value):
            best_value = value

    if best_value is None:
        return None
    return _CATEGORY_BY_VALUE.get(best_value, str(best_value))


def lookup_flood_risk(address: Optional[str]) -> dict:
    """Best-effort geocode + combined flood-hazard classification for a free-text address.

    Checks both river-flood and storm-surge datasets and combines them into a
    single headline result (whichever is more severe), alongside the two
    individual breakdowns.

    Returns {"latitude", "longitude", "flood_risk_flag", "flood_risk_category",
    "river_flood_category", "storm_surge_category"}. All 6 are None if the
    address is empty/blank or geocoding fails. If only one hazard dataset can
    be classified (e.g. the other's shapefile fails to load), the headline
    falls back to whichever result is available — this is a soft failure by
    design, never an exception, so it never blocks whatever is creating the
    underlying record.
    """
    empty = {
        "latitude": None,
        "longitude": None,
        "flood_risk_flag": None,
        "flood_risk_category": None,
        "river_flood_category": None,
        "storm_surge_category": None,
    }
    if not address or not address.strip():
        return empty

    try:
        coords = _geocode(address.strip())
        if coords is None:
            return empty
        lat, lng = coords

        river_category = _classify(lat, lng, _load_zones(RIVER_FLOOD_SHAPEFILE_PATH, RIVER_FLOOD_FIELD_NAME))
        storm_surge_category = _classify(lat, lng, _load_zones(STORM_SURGE_SHAPEFILE_PATH, STORM_SURGE_FIELD_NAME))

        if _SEVERITY[river_category] >= _SEVERITY[storm_surge_category]:
            combined_category = river_category
        else:
            combined_category = storm_surge_category

        return {
            "latitude": lat,
            "longitude": lng,
            "flood_risk_flag": combined_category is not None,
            "flood_risk_category": combined_category,
            "river_flood_category": river_category,
            "storm_surge_category": storm_surge_category,
        }
    except Exception:
        return empty
