"""Native Meteociel maps: declared radar frames and a lightning snapshot.

Only fixed upstream hosts are requested. No remote scripts or HTML are executed.
The user's source URL supplies the viewport, never the metadata request host.
"""
import asyncio
from datetime import datetime, timezone, timedelta
import json
import math
import re
from urllib.parse import parse_qs, urlsplit, urljoin, urlunsplit
from html.parser import HTMLParser

import aiohttp
from homeassistant.helpers.aiohttp_client import async_get_clientsession

RADAR_PAGE = "https://www.meteociel.fr/observations-meteo/radarzoom.php"
LIGHTNING_PAGE = "https://www.meteociel.fr/observations-meteo/foudre-direct.php"
STRIKES = "https://www.meteociel.fr/obs/foudre/temps-reel.php"


def viewport(url):
    """Read the supported source URL and reproduce the original 768px viewport."""
    parsed = urlsplit(url)
    paths = {urlsplit(RADAR_PAGE).path: ("radar", 6742.28, 9941.72, 4, 4),
             urlsplit(LIGHTNING_PAGE).path: ("lightning", 21246.45, 35533.4, 5.9, 6)}
    if (parsed.scheme != "https" or parsed.hostname != "www.meteociel.fr"
            or parsed.port not in (None, 443) or parsed.username or parsed.password
            or parsed.path not in paths):
        raise ValueError("Native Meteociel mode requires a supported Meteociel map URL")
    kind, x, y, zoom, maximum = paths[parsed.path]
    params = parse_qs(parsed.query)
    # Other radar products use different palettes and tile paths.
    if kind == "radar" and any(key in params for key in ("lame", "snow", "reflmf", "expert", "mode", "radar", "antenna")):
        raise ValueError("Only the standard precipitation radar is supported")
    values = [float(params.get(key, [default])[0]) for key, default in (("x", x), ("y", y), ("zoom", zoom))]
    x, y, zoom = values
    extent = 768 * 2 ** maximum
    if not all(math.isfinite(v) for v in values) or not (0 <= x <= extent and 0 <= y <= extent and 0 <= zoom <= maximum):
        raise ValueError("Invalid Meteociel viewport")
    scale = 2 ** (zoom - maximum)
    # Match Meteociel's boundary clamp, including its offset convention.
    left = (extent - 768 / scale) / 2 if extent * scale < 768 else max(0, min(x - 384, extent - 768 / scale))
    top = (extent - 768 / scale) / 2 if extent * scale < 768 else max(0, min(y - 384, extent - 768 / scale))
    return {"kind": kind, "x": left + 384, "y": top + 384, "left": left, "top": top,
            "zoom": zoom, "maximum": maximum, "scale": scale}


def tile_plan(view):
    """Bounded image requests and exact canvas rectangles, including fractional zoom."""
    level = min(view["maximum"], int(view["zoom"] + .9))
    size = 768 * 2 ** (view["maximum"] - level)
    count = 2 ** level
    result = []
    for y in range(max(0, int(view["top"] // size)), min(count - 1, int((view["top"] + 768 / view["scale"]) // size)) + 1):
        for x in range(max(0, int(view["left"] // size)), min(count - 1, int((view["left"] + 768 / view["scale"]) // size)) + 1):
            left, top = round((x * size - view["left"]) * view["scale"]), round((y * size - view["top"]) * view["scale"])
            right, bottom = round(((x + 1) * size - view["left"]) * view["scale"]), round(((y + 1) * size - view["top"]) * view["scale"])
            result.append({"x": x, "y": y, "level": level, "rect": [left, top, right - left, bottom - top]})
    return result


def radar_metadata(html, now=None):
    """Parse declared dates and palette, without evaluating upstream JavaScript."""
    now = now or datetime.now(timezone.utc)
    dates = sorted(set(re.findall(r'radardate2\[\d+\]\s*=\s*["\'](\d{12})["\']', html)))
    times = [datetime.strptime(value, "%Y%m%d%H%M").replace(tzinfo=timezone.utc) for value in dates]
    times = [value for value in times if value <= now][-12:]
    if not times:
        raise ValueError("No declared radar frames")
    colors = dict(re.findall(r'keyColors\[(\d+)\]\s*=\s*["\'](#[0-9A-Fa-f]{6})["\']', html))
    values = dict(re.findall(r'keyValues\[(\d+)\]\s*=\s*([0-9.]+)', html))
    palette = [{"color": colors[k], "value": float(values[k])} for k in sorted(colors, key=int) if k in values][:64]
    return {"times": [value.isoformat() for value in times], "palette": palette}


def projected_points(items, view, multiplier=64):
    result = []
    for item in items[:100000]:
        try:
            x, y = [(float(item[key]) * multiplier - view[origin]) * view["scale"] for key, origin in (("x", "left"), ("y", "top"))]
            age = float(item.get("d", 0))
        except (TypeError, ValueError, KeyError):
            continue
        if all(math.isfinite(v) for v in (x, y, age)) and -5 <= x <= 773 and -5 <= y <= 773 and 0 <= age <= 1800:
            result.append({"x": x, "y": y, "age": age})
    return result


async def read_source(session, url, params=None):
    """Bounded trusted metadata request; redirect responses are not followed."""
    async with session.get(url, params=params, allow_redirects=False, timeout=aiohttp.ClientTimeout(total=20), headers={"Cache-Control": "no-cache"}) as response:
        if response.status != 200:
            raise ValueError("Meteociel source unavailable")
        chunks, size = [], 0
        async for chunk in response.content.iter_chunked(32768):
            size += len(chunk)
            if size > 4 * 1024 * 1024:
                raise ValueError("Meteociel response too large")
            chunks.append(chunk)
        return b"".join(chunks).decode("utf-8", errors="replace")


async def city_labels(session, view):
    lightning = view["kind"] == "lightning"
    url = ("https://static.meteociel.fr/test/foudretiles/europe/getcities.php" if lightning
           else "https://modeles7.meteociel.fr/modeles/arome/tiles/getcities.php")
    try:
        data = json.loads(await read_source(session, url, {"zoom": view["zoom"], "offsetx": view["x"], "offsety": view["y"], "width": 768, "height": 768, "limit": 60, "size": 11}))
        labels = []
        for city in data[:1000]:
            x = (float(city["x"]) * (64 if lightning else 16) - view["left"]) * view["scale"]
            y = (float(city["y"]) * (64 if lightning else 16) - view["top"]) * view["scale"]
            if math.isfinite(x) and math.isfinite(y) and -30 <= x <= 768 and 0 <= y <= 768:
                labels.append({"x": x, "y": y, "name": str(city["n"])[:80]})
        return labels[:60]
    except (aiohttp.ClientError, TimeoutError, ValueError, TypeError, KeyError):
        return []


# Explicit page types and image selectors; user targets never become arbitrary hosts.
IMAGE_PAGES = {
    "/observations-meteo/humi.php": ("humidity", "obs_temps", "humi"),
    "/observations-meteo/rr.php": ("rain24", "obs_temps", "rr"),
    "/observations-meteo/vent-rafales.php": ("gusts", "obs_temps", "rafales"),
    "/observations-meteo/satellite.php": ("satellite", "satimg", None),
}


def source_spec(url):
    """Validate all native targets, retaining supported region/product choices."""
    parsed = urlsplit(url)
    if parsed.path not in IMAGE_PAGES:
        return viewport(url)
    if (parsed.scheme != "https" or parsed.hostname != "www.meteociel.fr"
            or parsed.port not in (None, 443) or parsed.username or parsed.password):
        raise ValueError("Use a supported HTTPS Meteociel map URL")
    kind, selector, prefix = IMAGE_PAGES[parsed.path]
    params = parse_qs(parsed.query, keep_blank_values=True)
    if set(params) - {"region", "mode"} or any(len(v) != 1 for v in params.values()):
        raise ValueError("Unsupported native Meteociel parameters")
    region = params.get("region", ["fr" if kind == "satellite" else ""])[0]
    if region and not re.fullmatch(r"[a-z0-9]{1,12}", region):
        raise ValueError("Invalid map region")
    mode = params.get("mode", ["animation-visible-composition-mtg" if kind == "satellite" else "0"])[0]
    if not re.fullmatch(r"[a-z0-9-]{1,80}", mode) or (kind != "satellite" and mode != "0") or (kind == "satellite" and "archive" in mode):
        raise ValueError("Unsupported native map product")
    request_params = {"region": region}
    if kind == "satellite" or kind == "gusts":
        request_params["mode"] = mode
    return {"kind": kind, "selector": selector, "prefix": prefix,
            "page": "https://www.meteociel.fr" + parsed.path, "params": request_params}


class MapImageParser(HTMLParser):
    """Extract only the named map image, never ads or arbitrary scripts."""
    def __init__(self, selector):
        super().__init__(convert_charrefs=True)
        self.selector = selector
        self.src = None

    def handle_starttag(self, tag, attrs):
        if tag != "img":
            return
        attrs = dict(attrs)
        if attrs.get("id") == self.selector or attrs.get("name") == self.selector:
            self.src = attrs.get("src")


def map_image_url(html, spec):
    """Reject unexpected hosts/paths even if upstream HTML is malformed."""
    parser = MapImageParser(spec["selector"])
    parser.feed(html)
    if not parser.src:
        raise ValueError("Missing Meteociel map image")
    url = urljoin(spec["page"], parser.src)
    parsed = urlsplit(url)
    if parsed.username or parsed.password or parsed.port not in (None, 443) or parsed.scheme not in ("http", "https") or parsed.query or parsed.fragment:
        raise ValueError("Unexpected map image URL")
    if spec["kind"] == "satellite":
        trusted = re.fullmatch(r"(?:modeles\d+|static|www)\.meteociel\.fr", parsed.hostname or "") and re.fullmatch(r"/satellite/[a-zA-Z0-9_-]+\.(?:gif|png|jpg|jpeg)", parsed.path)
    else:
        suffix = "_" + spec["params"]["region"] if spec["params"]["region"] else ""
        trusted = parsed.hostname in ("www.meteociel.fr", "static.meteociel.fr") and parsed.path == f'/cartes_obs/{spec["prefix"]}{suffix}.png'
    if not trusted:
        raise ValueError("Unexpected Meteociel image source")
    return urlunsplit(("https", parsed.netloc, parsed.path, "", ""))


async def async_image_map(session, runtime, card, spec):
    """Load the current original image/GIF; its timestamp stays embedded intact."""
    now = datetime.now(timezone.utc)
    key = (spec["page"], tuple(sorted(spec["params"].items())))
    async with runtime.setdefault("meteociel_image_lock", asyncio.Lock()):
        cache = runtime.setdefault("meteociel_image_cache", {})
        # Keep bounded metadata for personalized regions, shared between panels.
        cache = {k: v for k, v in cache.items() if (now - v["at"]).total_seconds() < 60}
        runtime["meteociel_image_cache"] = cache
        cached = cache.get(key)
        if not cached:
            html = await read_source(session, spec["page"], spec["params"])
            cached = {"at": now, "url": map_image_url(html, spec)}
            cache[key] = cached
    # The stable latest-file names must not reuse an old browser/proxy cache.
    image_url = cached["url"] + "?station_meteo_refresh=" + str(int(now.timestamp()))
    return {"kind": spec["kind"], "image_only": True, "embedded_time": True,
            "frames": [{"url": image_url, "time": None}], "source": card["url"],
            "animated": urlsplit(cached["url"]).path.endswith(".gif"),
            "credit": "Météociel / EUMETSAT — Meteosat12" if spec["kind"] == "satellite" else "Météociel — observations météo"}



async def async_meteociel(hass, runtime, index):
    """Get the latest observations when opened/refreshed, with a short shared cache."""
    card = runtime["config"]["map_buttons"][index]
    if card["mode"] != "meteociel" or not card["enabled"]:
        return {"frames": [], "error": "disabled"}
    try:
        view = source_spec(card["url"])
        if view["kind"] in ("humidity", "rain24", "gusts", "satellite"):
            return await async_image_map(async_get_clientsession(hass), runtime, card, view)
        plan = tile_plan(view)
        now = datetime.now(timezone.utc)
        session = async_get_clientsession(hass)
        async with runtime.setdefault("meteociel_lock", asyncio.Lock()):
            cache = runtime.setdefault("meteociel_cache", {})
            cached = cache.get(view["kind"])
            if not cached or (now - cached["at"]).total_seconds() > (30 if view["kind"] == "lightning" else 60):
                if view["kind"] == "radar":
                    content = radar_metadata(await read_source(session, RADAR_PAGE), now)
                else:
                    data = json.loads(await read_source(session, STRIKES, {"first": 1, "duree": 30, "region": "fr", "dontwait": 1, "modeloc": 1}))
                    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
                        raise ValueError("Invalid lightning observations")
                    content = {"items": data["items"], "time": now.isoformat()}
                cached = {"at": now, "content": content}
                cache[view["kind"]] = cached
        content = cached["content"]
        frames, backgrounds = [], []
        lightning = view["kind"] == "lightning"
        for tile in plan:
            level, x, y = tile["level"], tile["x"], tile["y"]
            url = (f"https://static.meteociel.fr/test/foudretiles/europe2/010_{level}_{x}_{y}.png" if lightning
                   else f"https://modeles14.meteociel.fr/test/arometiles/roads/111_{level}_{x}_{y}.png")
            backgrounds.append({"url": url, "rect": tile["rect"]})
        if lightning:
            time = content["time"]
            frames.append({"time": time, "tiles": [], "points": projected_points(content["items"], view)})
            start = (datetime.fromisoformat(time) - timedelta(minutes=30)).isoformat()
            credit = "Météociel / Blitzortung — 30 min"
        else:
            for time in content["times"]:
                value = datetime.fromisoformat(time)
                prefix = f'https://modeles14.meteociel.fr/radar/tiles/{value:%Y/%m/%d}'
                frames.append({"time": time, "tiles": [{"url": f'{prefix}/{tile["level"] + 1}/{value:%Y%m%d%H%M}-{tile["x"]}-{tile["y"]}.png', "rect": tile["rect"]} for tile in plan]})
            start = None
            credit = "Météociel — données Météo-France"
        labels = await city_labels(session, view)
        latest = datetime.fromisoformat(frames[-1]["time"])
        return {"kind": view["kind"], "frames": frames, "backgrounds": backgrounds, "labels": labels,
                "palette": content.get("palette", []), "start": start,
                "stale": (now - latest).total_seconds() > (300 if lightning else 3600),
                "source": card["url"], "credit": credit}
    except (aiohttp.ClientError, TimeoutError, ValueError, TypeError, KeyError, OverflowError):
        return {"frames": [], "error": "unavailable", "source": card["url"]}
