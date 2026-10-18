"""Recent EUMETSAT GeoColour imagery with dates from live WMS capabilities."""
import asyncio
from datetime import datetime, timedelta, timezone
import math
import re
from urllib.parse import urlencode
import xml.etree.ElementTree as ET

import aiohttp
from homeassistant.helpers.aiohttp_client import async_get_clientsession

WMS = "https://view.eumetsat.int/geoserver/wms"
LAYER = "mtg_fd:rgb_geocolour"
NAMESPACE = {"w": "http://www.opengis.net/wms"}


def recent_times(xml, now=None):
    """Select the twelve most recent declared frames, without invented dates."""
    root = ET.fromstring(xml)
    now = now or datetime.now(timezone.utc)
    dimension = None
    for layer in root.findall(".//w:Layer", NAMESPACE):
        if layer.findtext("w:Name", "", NAMESPACE) == LAYER:
            dimension = next((node for node in layer.findall("w:Dimension", NAMESPACE) if node.get("name") == "time"), None)
            break
    if dimension is None or not dimension.text:
        raise ValueError("Missing satellite time dimension")
    def stamp(s):
        return datetime.fromisoformat(s.strip().replace("Z", "+00:00")).astimezone(timezone.utc)
    text = dimension.text.strip()
    if "/" in text and "," not in text:
        start, end, period = text.split("/")
        match = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", period)
        if not match:
            raise ValueError("Unsupported satellite cadence")
        step = timedelta(hours=int(match[1] or 0), minutes=int(match[2] or 0), seconds=int(match[3] or 0))
        if not timedelta(seconds=1) <= step <= timedelta(hours=6):
            raise ValueError("Invalid satellite cadence")
        start, end = stamp(start), min(stamp(end), now)
        latest = start + ((end - start) // step) * step
        dates = [latest - i * step for i in range(11, -1, -1) if latest - i * step >= start]
    else:
        dates = sorted({stamp(value) for value in text.split(",") if stamp(value) <= now})[-12:]
    if not dates:
        raise ValueError("No recent satellite imagery")
    return [d.isoformat().replace("+00:00", "Z") for d in dates]


def image_urls(times, latitude, longitude, zoom):
    """Use a fixed trusted WMS source; crop settings never become request hosts."""
    span = 360 / 2 ** zoom
    height = span * .625 * math.cos(math.radians(latitude))
    south, north = max(-77, latitude - height / 2), min(77, latitude + height / 2)
    west, east = max(-77, longitude - span / 2), min(77, longitude + span / 2)
    if south >= north or west >= east:
        raise ValueError("Outside Meteosat GeoColour coverage")
    common = dict(SERVICE="WMS", VERSION="1.1.1", REQUEST="GetMap", LAYERS=LAYER,
                  STYLES="", SRS="EPSG:4326", BBOX=f"{west},{south},{east},{north}",
                  WIDTH=960, HEIGHT=600, FORMAT="image/jpeg")
    return [{"time": value, "url": WMS + "?" + urlencode({**common, "TIME": value})} for value in times]


async def async_satellite(hass, runtime, index):
    """Cache source metadata for one minute, shared by all connected panels."""
    cfg = runtime["config"]
    if not 0 <= index < len(cfg["map_buttons"]):
        return {"frames": [], "error": "disabled"}
    card = cfg["map_buttons"][index]
    if card["mode"] != "satellite" or not card["enabled"]:
        return {"frames": [], "error": "disabled"}
    now = datetime.now(timezone.utc)
    try:
        async with runtime.setdefault("satellite_lock", asyncio.Lock()):
            cache = runtime.get("satellite_cache")
            if not cache or (now - cache["at"]).total_seconds() > 60:
                session = async_get_clientsession(hass)
                async with session.get(WMS, params={"SERVICE": "WMS", "REQUEST": "GetCapabilities", "VERSION": "1.3.0"}, timeout=aiohttp.ClientTimeout(total=20)) as response:
                    response.raise_for_status()
                    chunks, size = [], 0
                    async for chunk in response.content.iter_chunked(32768):
                        size += len(chunk)
                        if size > 2 * 1024 * 1024:
                            raise ValueError("Satellite metadata too large")
                        chunks.append(chunk)
                times = recent_times(b"".join(chunks), now)
                cache = {"at": now, "times": times}
                runtime["satellite_cache"] = cache
        latitude = card["latitude"]
        longitude = card["longitude"]
        if latitude is None:
            latitude = hass.config.latitude if cfg.get("latitude") is None else cfg["latitude"]
        if longitude is None:
            longitude = hass.config.longitude if cfg.get("longitude") is None else cfg["longitude"]
        frames = image_urls(cache["times"], latitude, longitude, card["zoom"])
        latest = datetime.fromisoformat(cache["times"][-1].replace("Z", "+00:00"))
        return {"frames": frames, "stale": (now - latest).total_seconds() > 10800,
                "source": "https://view.eumetsat.int/", "credit": "EUMETSAT / NASA — GeoColour"}
    except (aiohttp.ClientError, TimeoutError, ValueError, ET.ParseError):
        return {"frames": [], "error": "unavailable", "source": "https://view.eumetsat.int/"}
