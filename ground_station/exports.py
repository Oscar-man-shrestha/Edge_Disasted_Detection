"""Mission exports: CSV, GeoJSON, KML (Google Earth) and the printable report's numbers."""
import csv
import io
import math
from xml.sax.saxutils import escape

CSV_COLS = ["id", "mission_id", "type", "conf", "status", "lat", "lon",
            "wall_time", "received", "note", "snapshot"]
TYPES = ("person", "fire", "smoke")
KML_COLORS = {"person": "ffe58739", "fire": "ff2659d9", "smoke": "ff709e19"}   # aabbggrr


def _located(a):
    return a.get("lat") is not None and a.get("lon") is not None


def to_csv(alerts):
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(CSV_COLS)
    for a in alerts:
        w.writerow(["" if a.get(c) is None else a.get(c) for c in CSV_COLS])
    return out.getvalue()


def to_geojson(alerts, track):
    feats = []
    for a in alerts:
        if not _located(a):
            continue
        feats.append({"type": "Feature",
                      "geometry": {"type": "Point", "coordinates": [a["lon"], a["lat"]]},
                      "properties": {k: a.get(k) for k in
                                     ("id", "type", "conf", "status", "wall_time", "note")}})
    if len(track) >= 2:
        feats.append({"type": "Feature",
                      "geometry": {"type": "LineString",
                                   "coordinates": [[p["lon"], p["lat"]] for p in track]},
                      "properties": {"kind": "track"}})
    return {"type": "FeatureCollection", "features": feats}


def to_kml(mission, alerts, track):
    e = lambda v: escape("" if v is None else str(v))
    parts = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>',
             "<name>%s</name>" % e(mission.get("name"))]
    for t in TYPES:
        parts.append('<Style id="%s"><IconStyle><color>%s</color><scale>1.2</scale></IconStyle></Style>'
                     % (t, KML_COLORS[t]))
    parts.append('<Style id="track"><LineStyle><color>ff00d7ff</color><width>3</width></LineStyle></Style>')
    for a in alerts:
        if not _located(a):
            continue
        desc = "conf %.2f · %s · %s%s" % (a["conf"], a.get("status"), a.get("wall_time") or "",
                                           (" · " + a["note"]) if a.get("note") else "")
        parts.append("<Placemark><name>%s #%s</name><description>%s</description>"
                     "<styleUrl>#%s</styleUrl><Point><coordinates>%f,%f,0</coordinates></Point>"
                     "</Placemark>" % (e(a["type"]), a["id"], e(desc), e(a["type"]),
                                       a["lon"], a["lat"]))
    if len(track) >= 2:
        coords = " ".join("%f,%f,0" % (p["lon"], p["lat"]) for p in track)
        parts.append("<Placemark><name>Flight track</name><styleUrl>#track</styleUrl>"
                     "<LineString><tessellate>1</tessellate><coordinates>%s</coordinates>"
                     "</LineString></Placemark>" % coords)
    parts.append("</Document></kml>")
    return "\n".join(parts)


def _dist_m(a, b):
    dlat = (b["lat"] - a["lat"]) * 111320.0
    dlon = (b["lon"] - a["lon"]) * 111320.0 * math.cos(math.radians((a["lat"] + b["lat"]) / 2))
    return math.hypot(dlat, dlon)


def report_context(mission, alerts, track):
    counts = {t: {"total": 0, "new": 0, "acknowledged": 0, "resolved": 0} for t in TYPES}
    first = {}
    for a in sorted(alerts, key=lambda x: x["id"]):
        c = counts.setdefault(a["type"], {"total": 0, "new": 0, "acknowledged": 0, "resolved": 0})
        c["total"] += 1
        c[a.get("status") or "new"] = c.get(a.get("status") or "new", 0) + 1
        first.setdefault(a["type"], a.get("wall_time"))
    pts = list(track) + [a for a in alerts if _located(a)]
    bbox = None
    if pts:
        bbox = [min(p["lat"] for p in pts), min(p["lon"] for p in pts),
                max(p["lat"] for p in pts), max(p["lon"] for p in pts)]
    return {
        "duration_s": (track[-1]["t"] - track[0]["t"]) if len(track) >= 2 else None,
        "distance_m": sum(_dist_m(a, b) for a, b in zip(track, track[1:])),
        "counts": counts,
        "first_detection": first,
        "bbox": bbox,
    }
