"""Native Meteociel maps: declared radar frames and a lightning snapshot.

Only fixed upstream hosts are requested. No remote scripts or HTML are executed.
The user's source URL supplies the viewport, never the metadata request host.
"""
import asyncio
from datetime import datetime, timezone, timedelta
import json
import math
import logging
import re
from urllib.parse import parse_qs, urlsplit, urljoin, urlunsplit
from html.parser import HTMLParser

import aiohttp
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

RADAR_PAGE = "https://www.meteociel.fr/observations-meteo/radarzoom.php"
LIGHTNING_PAGE = "https://www.meteociel.fr/observations-meteo/foudre-direct.php"
STRIKES = "https://www.meteociel.fr/obs/foudre/temps-reel.php"
ACCUMULATIONS = {5: '5m_', 15: '5m_', 1: '', 3: '12h_', 2: '24h_', 6: '48h_', 7: '72h_', 4: 'clim6z_'}


def viewport(url, requested=None):
    """Read the supported source URL and reproduce the original 768px viewport."""
    parsed = urlsplit(url)
    paths = {urlsplit(RADAR_PAGE).path: ("radar", 6742.28, 9941.72, 4, 4),
             urlsplit(LIGHTNING_PAGE).path: ("lightning", 21246.45, 35533.4, 5.9, 6)}
    if (parsed.scheme != "https" or parsed.hostname != "www.meteociel.fr"
            or parsed.port not in (None, 443) or parsed.username or parsed.password
            or parsed.path not in paths):
        raise ValueError("Native Meteociel mode requires a supported Meteociel map URL")
    kind, x, y, zoom, maximum = paths[parsed.path]
    params = parse_qs(parsed.query, keep_blank_values=True)
    # Other radar products use different palettes and tile paths.
    if kind == "radar" and any(key in params for key in ("snow", "reflmf", "expert", "mode", "radar", "antenna", "archive")):
        raise ValueError("Unsupported radar product")
    product = 0
    if kind == "radar" and "lame" in params:
        if len(params["lame"]) != 1 or params["lame"][0] not in {str(v) for v in ACCUMULATIONS}:
            raise ValueError("Unsupported accumulation product")
        product = int(params["lame"][0])
    if requested is not None:
        if not isinstance(requested, dict) or set(requested) != {"x", "y", "zoom"} or any(type(v) not in (int, float) for v in requested.values()):
            raise ValueError("Invalid map navigation")
    values = [float(requested[key] if requested is not None else params.get(key, [default])[0]) for key, default in (("x", x), ("y", y), ("zoom", zoom))]
    x, y, zoom = values
    extent = 768 * 2 ** maximum
    if not all(math.isfinite(v) for v in values) or not (0 <= x <= extent and 0 <= y <= extent and 0 <= zoom <= maximum):
        raise ValueError("Invalid Meteociel viewport")
    scale = 2 ** (zoom - maximum)
    # Match Meteociel's boundary clamp, including its offset convention.
    left = (extent - 768 / scale) / 2 if extent * scale < 768 else max(0, min(x - 384, extent - 768 / scale))
    top = (extent - 768 / scale) / 2 if extent * scale < 768 else max(0, min(y - 384, extent - 768 / scale))
    return {"kind": kind, "x": left + 384, "y": top + 384, "left": left, "top": top,
            "zoom": zoom, "maximum": maximum, "scale": scale, "product": product}


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


def accumulation_metadata(html, product, now=None):
    """Read observed accumulations and declared PIAF forecast frames, never JS."""
    now = now or datetime.now(timezone.utc)
    content = radar_metadata(html, now)
    dates = dict(re.findall(r'radardate2\[(\d+)\]\s*=\s*["\'](\d{4}|\d{12})["\']', html))
    folders = dict(re.findall(r'radardate\[(\d+)\]\s*=\s*["\']([0-9/]+)["\']', html))
    match = re.search(r'var\s+piafFirstEch\s*=\s*(\d+)', html)
    forecast_index = int(match[1]) if match and product == 15 else 9999
    specs, previous = [], None
    for index in sorted(dates, key=int)[:96]:
        token, folder = dates[index], folders.get(index, '')
        forecast = int(index) >= forecast_index
        if not forecast:
            if len(token) != 12:
                continue
            time = datetime.strptime(token, '%Y%m%d%H%M').replace(tzinfo=timezone.utc)
            if time > now or folder != time.strftime('%Y/%m/%d'):
                continue
        else:
            if previous is None or len(token) != 4 or not re.fullmatch(r'\d{1,6}', folder):
                continue
            time = previous.replace(hour=int(token[:2]), minute=int(token[2:]))
            if time <= previous:
                time += timedelta(days=1)
            if (time-datetime.fromisoformat(content['times'][-1])).total_seconds() > 3*3600:
                continue
        previous = time
        specs.append({'time': time.isoformat(), 'token': token, 'folder': folder, 'forecast': forecast})
    if not specs:
        raise ValueError('No declared accumulation frames')
    content['frame_specs'] = specs
    return content


def projected_points(items, view, multiplier=64, minutes=30):
    result = []
    for item in items[:100000]:
        try:
            x, y = [(float(item[key]) * multiplier - view[origin]) * view["scale"] for key, origin in (("x", "left"), ("y", "top"))]
            age = float(item.get("d", 0))
        except (TypeError, ValueError, KeyError):
            continue
        if all(math.isfinite(v) for v in (x, y, age)) and -5 <= x <= 773 and -5 <= y <= 773 and 0 <= age <= minutes * 60:
            result.append({"x": x, "y": y, "age": age, "id": str(item.get("_id", ""))[:100]})
    return result


async def read_source(session, url, params=None):
    """Bounded trusted metadata request; redirect responses are not followed."""
    async with session.get(url, params=params, allow_redirects=False, timeout=aiohttp.ClientTimeout(total=20), headers={"Cache-Control": "no-cache"}) as response:
        if response.status != 200:
            raise ValueError(f"Meteociel source unavailable (HTTP {response.status})")
        chunks, size = [], 0
        async for chunk in response.content.iter_chunked(32768):
            size += len(chunk)
            if size > 4 * 1024 * 1024:
                raise ValueError("Meteociel response too large")
            chunks.append(chunk)
        return b"".join(chunks).decode("utf-8", errors="replace")


async def city_labels(session, view, density=None):
    lightning = view["kind"] == "lightning"
    if density == 0:
        return []
    limit = {1: 20000, 2: 5000, 3: 0}.get(density, 60)
    url = ("https://static.meteociel.fr/test/foudretiles/europe/getcities.php" if lightning
           else "https://modeles7.meteociel.fr/modeles/arome/tiles/getcities.php")
    try:
        data = json.loads(await read_source(session, url, {"zoom": view["zoom"], "offsetx": view["x"], "offsety": view["y"], "width": 768, "height": 768, "limit": limit, "size": 11}))
        labels = []
        for city in data[:10000]:
            x = (float(city["x"]) * (64 if lightning else 16) - view["left"]) * view["scale"]
            y = (float(city["y"]) * (64 if lightning else 16) - view["top"]) * view["scale"]
            if math.isfinite(x) and math.isfinite(y) and -30 <= x <= 768 and 0 <= y <= 768:
                labels.append({"x": x, "y": y, "name": str(city["n"])[:80]})
        return labels[:10000]
    except (aiohttp.ClientError, TimeoutError, ValueError, TypeError, KeyError):
        return []


# Explicit page types and image selectors; user targets never become arbitrary hosts.
IMAGE_PAGES = {
    "/observations-meteo/radar2.php": ("radar_animation", "img", None),
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
    if set(params) - ({"region", "mode", "freq"} if kind == "radar_animation" else {"region", "mode"}) or any(len(v) != 1 for v in params.values()):
        raise ValueError("Unsupported native Meteociel parameters")
    region = params.get("region", ["fr" if kind in ("satellite", "radar_animation") else ""])[0]
    if region and not re.fullmatch(r"[a-z0-9]{1,12}", region):
        raise ValueError("Invalid map region")
    mode = params.get("mode", ["animation-visible-composition-mtg" if kind == "satellite" else "0"])[0]
    if not re.fullmatch(r"[a-z0-9-]{1,80}", mode) or (kind not in ("satellite", "radar_animation") and mode != "0") or (kind == "satellite" and "archive" in mode):
        raise ValueError("Unsupported native map product")
    if kind == "radar_animation":
        if region not in {"fr", "no", "ne", "so", "se", "re", "re2", "ant1", "ant2", "ant3", "uk", "de", "sp", "it", "na"}:
            raise ValueError("Unsupported radar region")
        if mode not in {"0", "1"}:
            raise ValueError("Unsupported radar product")
        frequency = params.get("freq", ["5"])[0]
        if frequency not in {"5", "15"}:
            raise ValueError("Unsupported radar frequency")
        return {"kind": kind, "selector": selector, "prefix": None,
                "page": "https://www.meteociel.fr" + parsed.path,
                "params": {"region": region, "mode": mode, "freq": frequency}}
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
    elif spec["kind"] == "radar_animation":
        region = re.escape(spec["params"]["region"])
        product = "lastsnowradar" if spec["params"]["mode"] == "1" else "lastradar"
        frequency = "5m" if spec["params"]["freq"] == "5" else ""
        trusted = parsed.hostname in ("www.meteociel.fr", "static.meteociel.fr") and re.fullmatch(rf"/cartes_obs/radar/{product}{frequency}_{region}\.gif", parsed.path)
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



def lightning_options(options=None):
    defaults = {'duration': 30, 'cities': 1, 'roads': False, 'rivers': True, 'relief': False}
    if options is None:
        return defaults
    if not isinstance(options, dict) or set(options) - set(defaults):
        raise ValueError('Invalid lightning options')
    values = {**defaults, **options}
    if type(values['duration']) is not int or values['duration'] not in (2, 5, 10, 30, 60, 120):
        raise ValueError('Invalid lightning duration')
    if type(values['cities']) is not int or values['cities'] not in (0, 1, 2, 3):
        raise ValueError('Invalid city density')
    if any(type(values[k]) is not bool for k in ('roads', 'rivers', 'relief')):
        raise ValueError('Invalid lightning layer')
    return values


async def lightning_snapshot(session, cached, now, minutes):
    """Follow the upstream incremental cursor; stable IDs prevent repeated sounds."""
    last = cached['content'].get('last') if cached else None
    if last == '0':
        last = None
    params = {'last': last} if last else {'first': 1, 'duree': minutes}
    params.update(region='fr', dontwait=1, modeloc=1)
    reset = False
    try:
        text = await read_source(session, STRIKES, params)
        data = {'items': [], 'last': last or '0'} if text.strip() == 'NO' else json.loads(text)
        if not isinstance(data, dict) or not isinstance(data.get('items'), list):
            raise ValueError('Invalid lightning observations')
        cursor = str(data.get('last', '')).strip()
        if not re.fullmatch(r'[0-9]{1,32}', cursor):
            raise ValueError('Invalid lightning cursor')
    except (ValueError, aiohttp.ClientError, TimeoutError):
        if not last:
            raise
        # A cursor may expire or the upstream feed may restart. Reopen the
        # selected history window once instead of retrying a broken cursor forever.
        text = await read_source(session, STRIKES, {'first': 1, 'duree': minutes, 'region': 'fr', 'dontwait': 1, 'modeloc': 1})
        data = {'items': [], 'last': '0'} if text.strip() == 'NO' else json.loads(text)
        if not isinstance(data, dict) or not isinstance(data.get('items'), list):
            raise ValueError('Invalid lightning observations')
        cursor = str(data.get('last', '')).strip()
        if not re.fullmatch(r'[0-9]{1,32}', cursor):
            raise ValueError('Invalid lightning cursor')
        cached, last, reset = None, None, True
    items = []
    if cached and last:
        elapsed = max(0, (now-cached['at']).total_seconds())
        for item in cached['content']['items']:
            try:
                age = float(item['d'])+elapsed
            except (TypeError, ValueError, KeyError):
                continue
            if math.isfinite(age) and 0 <= age <= minutes*60:
                items.append({**item, 'd': age})
    # The cursor identifies each upstream batch. Retain IDs across subsequent
    # refreshes and layer/city changes, instead of comparing moving ages.
    if not cached or cursor != last:
        for index, item in enumerate(data['items'][:100000]):
            if isinstance(item, dict):
                items.append({**item, '_id': f'{cursor}:{index}'})
    return {'items': items[-100000:], 'last': cursor, 'time': now.isoformat(), 'reset': reset}


async def async_meteociel(hass, runtime, index, options=None, requested_view=None, product=None):
    """Get the latest observations when opened/refreshed, with a short shared cache."""
    if not 0 <= index < len(runtime["config"]["map_buttons"]):
        return {"frames": [], "error": "disabled"}
    card = runtime["config"]["map_buttons"][index]
    if card["mode"] != "meteociel" or not card["enabled"]:
        return {"frames": [], "error": "disabled"}
    try:
        view = source_spec(card["url"])
        if requested_view is not None:
            view = viewport(card["url"], requested_view)
        selected = view.get('product', 0)
        if product is not None:
            if view['kind'] != 'radar' or type(product) is not int or product not in ACCUMULATIONS:
                raise ValueError('Unsupported accumulation product')
            selected = product
        if view["kind"] == "radar":
            view = {**view, "product": selected}
        settings = lightning_options({"cities": 3, "roads": True, "rivers": True, "relief": True, **(options or {})} if view["kind"] == "radar" else options)
        if view["kind"] in ("humidity", "rain24", "gusts", "satellite", "radar_animation"):
            return await async_image_map(async_get_clientsession(hass), runtime, card, view)
        plan = tile_plan(view)
        now = datetime.now(timezone.utc)
        session = async_get_clientsession(hass)
        async with runtime.setdefault("meteociel_lock", asyncio.Lock()):
            cache = runtime.setdefault("meteociel_cache", {})
            key = ('lightning', settings['duration']) if view['kind'] == 'lightning' else ('radar', selected) if selected else view['kind']
            cached = cache.get(key)
            if not cached or (now - cached["at"]).total_seconds() > (30 if view["kind"] == "lightning" else 60):
                if view["kind"] == "radar":
                    if selected:
                        content = accumulation_metadata(await read_source(session, RADAR_PAGE, {'lame': selected}), selected, now)
                    else:
                        content = radar_metadata(await read_source(session, RADAR_PAGE), now)
                else:
                    content = await lightning_snapshot(session, cached, now, settings['duration'])
                cached = {"at": now, "content": content}
                cache[key] = cached
        content = cached["content"]
        frames, backgrounds = [], []
        lightning = view["kind"] == "lightning"
        for tile in plan:
            # The radar viewer omits the overlay entirely for mask 000;
            # that file does not exist on the upstream tile server.
            if not lightning and not any(settings[key] for key in ("roads", "rivers", "relief")):
                continue
            level, x, y = tile["level"], tile["x"], tile["y"]
            url = (f"https://static.meteociel.fr/test/foudretiles/europe2/{int(settings['relief'])}{int(settings['rivers'])}{int(settings['roads'])}_{level}_{x}_{y}.png" if lightning
                   else f"https://modeles14.meteociel.fr/test/arometiles/roads/{int(settings['relief'])}{int(settings['rivers'])}{int(settings['roads'])}_{level}_{x}_{y}.png")
            backgrounds.append({"url": url, "rect": tile["rect"]})
        if lightning:
            time = content["time"]
            frames.append({"time": time, "tiles": [], "points": projected_points(content["items"], view, minutes=settings["duration"])})
            start = (datetime.fromisoformat(time) - timedelta(minutes=settings["duration"])).isoformat()
            credit = f"Météociel / Blitzortung — {settings['duration']} min"
        else:
            for spec in content.get('frame_specs', [{'time': time, 'forecast': False} for time in content['times']]):
                time = spec['time']
                value = datetime.fromisoformat(time)
                folder = spec.get('folder', value.strftime('%Y/%m/%d'))
                prefix = f'https://modeles14.meteociel.fr/radar/{"tilespiaf" if spec["forecast"] else "tileslame" if selected else "tiles"}/{folder}'
                token = spec.get('token', value.strftime('%Y%m%d%H%M'))
                token = (ACCUMULATIONS[selected] if selected and not spec['forecast'] else '') + token
                frames.append({"time": time, "forecast": spec['forecast'], "tiles": [{"url": f'{prefix}/{tile["level"] + 1}/{token}-{tile["x"]}-{tile["y"]}.png', "rect": tile["rect"]} for tile in plan]})
            start = None
            credit = "Météociel — données Météo-France"
        labels = await city_labels(session, view, settings["cities"])
        latest = datetime.fromisoformat(content['times'][-1] if view['kind'] == 'radar' else frames[-1]['time'])
        return {"kind": view["kind"], "viewport": view, "frames": frames, "backgrounds": backgrounds, "labels": labels,
                "product": selected, "unit": 'mm' if selected else 'mm/h',
                "palette": content.get("palette", []), "start": start,
                "duration": settings["duration"] if lightning else None,
                "reset": bool(lightning and content.get('reset')),
                "stale": (now - latest).total_seconds() > (300 if lightning else 3600),
                "source": card["url"], "credit": credit}
    except (aiohttp.ClientError, TimeoutError, ValueError, TypeError, KeyError, OverflowError) as error:
        _LOGGER.warning('Meteociel map unavailable: %s: %s', type(error).__name__, error)
        status = re.search(r'HTTP ([0-9]{3})', str(error))
        return {"frames": [], "error": "unavailable", "reason": 'http_'+status[1] if status else 'timeout' if isinstance(error, TimeoutError) else 'network' if isinstance(error, aiohttp.ClientError) else 'source', "source": card["url"]}
