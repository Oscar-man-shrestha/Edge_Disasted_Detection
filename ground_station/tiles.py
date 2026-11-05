"""Offline map tiles: a caching proxy for OpenStreetMap plus a polite prefetch tool.

Every tile the dashboard shows while online is saved, so visiting the flight area
once at home makes it available in the field. To prefetch an area explicitly:

    python ground_station/tiles.py prefetch --bbox 12.965,77.585,12.978,77.598 --zoom 14-18

OSM tile policy: identify the app, no bulk downloading. Hence the 3000-tile cap,
zoom <= 18 for prefetch and one request at a time with a delay.
"""
import argparse
import math
import os
import sys
import tempfile
import time

from flask import Blueprint, abort, send_file

TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
# AWS Open Data "Terrain Tiles" (Mapzen), Terrarium-encoded elevation PNGs, zoom 0-15
TERRAIN_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
MAX_ZOOM_TERRAIN = 15
USER_AGENT = "EdgeDisasterGS/1.0 (+https://github.com/Hisana-07/Edge_Disasted_Detection_Project)"
MAX_ZOOM_SERVE = 19
MAX_ZOOM_PREFETCH = 18
MAX_PREFETCH = 3000
PREFETCH_DELAY_S = 0.2
DEFAULT_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "received", "tiles")
DEFAULT_TERRAIN_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "received", "terrain")


def osm_fetch(z, x, y):
    return _fetch(TILE_URL, z, x, y)


def terrain_fetch(z, x, y):
    return _fetch(TERRAIN_URL, z, x, y)


def _fetch(url, z, x, y):
    import requests
    try:
        r = requests.get(url.format(z=z, x=x, y=y), timeout=(2, 5),
                         headers={"User-Agent": USER_AGENT})
    except requests.RequestException:
        return None
    return r.content if r.status_code == 200 and r.content else None


def _valid(z, x, y, max_zoom=MAX_ZOOM_SERVE):
    return 0 <= z <= max_zoom and 0 <= x < 2 ** z and 0 <= y < 2 ** z


def _path(cache_dir, z, x, y):
    return os.path.join(cache_dir, str(z), str(x), "%d.png" % y)


def _save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".part")
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


OFFLINE_BACKOFF_S = 30.0


def tiles_blueprint(cache_dir, fetch=None, name="tiles", url_prefix="/tiles", max_zoom=MAX_ZOOM_SERVE):
    fetch = fetch or osm_fetch
    bp = Blueprint(name, __name__)
    offline_until = [0.0]          # after a failed fetch, serve cache-only for a while:
                                   # hung lookups would tie up the browser's few connections

    @bp.route(url_prefix + "/<int:z>/<int:x>/<int:y>.png")
    def tile(z, x, y):
        if not _valid(z, x, y, max_zoom):
            abort(404)
        path = _path(cache_dir, z, x, y)
        if not os.path.isfile(path):
            if time.time() < offline_until[0]:
                abort(404)                       # recently offline: don't try the internet again yet
            data = fetch(z, x, y)
            if not data:
                offline_until[0] = time.time() + OFFLINE_BACKOFF_S
                abort(404)                       # offline and not cached: blank tile
            _save(path, data)
        resp = send_file(path, mimetype="image/png")
        resp.headers["Cache-Control"] = "public, max-age=86400"
        return resp

    return bp


def _xy(lat, lon, z):
    lat = max(min(lat, 85.0511), -85.0511)
    n = 2 ** z
    x = int((lon + 180.0) / 360.0 * n)
    r = math.radians(lat)
    y = int((1.0 - math.log(math.tan(r) + 1.0 / math.cos(r)) / math.pi) / 2.0 * n)
    return min(max(x, 0), n - 1), min(max(y, 0), n - 1)


def tile_range(lat1, lon1, lat2, lon2, zmin, zmax):
    out = []
    for z in range(zmin, zmax + 1):
        x1, y1 = _xy(max(lat1, lat2), min(lon1, lon2), z)     # north-west corner
        x2, y2 = _xy(min(lat1, lat2), max(lon1, lon2), z)     # south-east corner
        for x in range(x1, x2 + 1):
            for y in range(y1, y2 + 1):
                out.append((z, x, y))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Offline map tile cache")
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("prefetch", help="download an area's tiles into the cache")
    p.add_argument("--bbox", required=True, help="lat1,lon1,lat2,lon2")
    p.add_argument("--zoom", default="14-17", help="e.g. 15 or 14-18 (max 18)")
    p.add_argument("--cache-dir", default=DEFAULT_CACHE)
    p.add_argument("--terrain-cache-dir", default=DEFAULT_TERRAIN_CACHE)
    p.add_argument("--terrain", action="store_true", help="also fetch 3D terrain tiles (zoom <= 15)")
    p.add_argument("--dry-run", action="store_true", help="only count tiles")
    a = ap.parse_args(argv)
    if a.cmd != "prefetch":
        ap.print_help()
        return 1
    lat1, lon1, lat2, lon2 = [float(v) for v in a.bbox.split(",")]
    zs = [int(v) for v in a.zoom.split("-")]
    zmin, zmax = zs[0], zs[-1]
    if zmax > MAX_ZOOM_PREFETCH:
        print("refusing: zoom above %d (OSM tile policy)" % MAX_ZOOM_PREFETCH)
        return 2
    # jobs: (z, x, y, cache_dir, fetch)
    jobs = [t + (a.cache_dir, osm_fetch) for t in tile_range(lat1, lon1, lat2, lon2, zmin, zmax)]
    if a.terrain:
        tz = min(zmax, MAX_ZOOM_TERRAIN)
        jobs += [t + (a.terrain_cache_dir, terrain_fetch)
                 for t in tile_range(lat1, lon1, lat2, lon2, min(zmin, tz), tz)]
    if len(jobs) > MAX_PREFETCH:
        print("refusing: %d tiles > %d. Use a smaller area or fewer zoom levels."
              % (len(jobs), MAX_PREFETCH))
        return 2
    todo = [j for j in jobs if not os.path.isfile(_path(j[3], *j[:3]))]
    print("%d tiles in area%s, %d not cached yet"
          % (len(jobs), " (map + terrain)" if a.terrain else "", len(todo)))
    if a.dry_run:
        return 0
    got = 0
    for i, (z, x, y, cache, fetch) in enumerate(todo, 1):
        data = fetch(z, x, y)
        if data:
            _save(_path(cache, z, x, y), data)
            got += 1
        if i % 50 == 0 or i == len(todo):
            print("  %d/%d" % (i, len(todo)))
        time.sleep(PREFETCH_DELAY_S)
    print("downloaded %d tiles" % got)
    return 0

if __name__ == "__main__":
    sys.exit(main())
