"""Local astronomy and daily, date-checked almanac excerpts."""
import asyncio
from datetime import datetime, timezone
from html.parser import HTMLParser
import re
from zoneinfo import ZoneInfo

import aiohttp
from astral import Observer
import ephem
from astral.sun import sunrise, sunset, noon
from homeassistant.helpers.aiohttp_client import async_get_clientsession

SOURCE = "https://www.ephemeride-jour.fr/"


class AlmanacParser(HTMLParser):
    """Read text from the provider's summary cards, never its HTML markup."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.cards = []
        self.depth = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        classes = dict(attrs).get("class", "").split()
        if tag == "div":
            if self.depth:
                self.depth += 1
            elif "hero-card" in classes:
                self.depth = 1
                self.parts = []

    def handle_endtag(self, tag):
        if tag == "div" and self.depth:
            self.depth -= 1
            if not self.depth:
                self.cards.append(" ".join(" ".join(self.parts).split()))

    def handle_data(self, data):
        if self.depth:
            self.parts.append(data)


def parse_almanac(html, day):
    """Reject yesterday's page and incomplete/unexpected layouts."""
    dates = re.findall(r'"dateModified"\s*:\s*"(\d{4}-\d{2}-\d{2})', html)
    if day.isoformat() not in dates:
        raise ValueError("Almanac date does not match today")
    parser = AlmanacParser()
    parser.feed(html)
    result = {}
    for card in parser.cards:
        for label, key in (("Saint du jour", "saint"), ("Dicton du jour", "saying"), ("Citation", "quote")):
            if label in card:
                result[key] = card.split(label, 1)[1].strip()[:600]
    if not all(result.get(key) for key in ("saint", "saying", "quote")):
        raise ValueError("Missing almanac cards")
    return {"date": day.isoformat(), "source": SOURCE, **result}


def astronomy(hass, config, now=None):
    """Calculate for the configured observer and local calendar date."""
    zone = ZoneInfo(hass.config.time_zone)
    now = now or datetime.now(zone)
    day = now.astimezone(zone).date()
    latitude = config.get("latitude")
    longitude = config.get("longitude")
    observer = Observer(
        hass.config.latitude if latitude is None else latitude,
        hass.config.longitude if longitude is None else longitude,
        config["altitude"],
    )
    result = {"date": day.isoformat()}
    for key, calc in (("sunrise", sunrise), ("sunset", sunset), ("noon", noon)):
        try:
            result[key] = calc(observer, date=day, tzinfo=zone).isoformat()
        except ValueError:  # Polar day/night: no invented rise or set time.
            result[key] = None
    moment = ephem.Date(now.astimezone(timezone.utc).replace(tzinfo=None))
    previous = ephem.previous_new_moon(moment)
    following = ephem.next_new_moon(moment)
    fraction = float(moment - previous) / float(following - previous)
    names = ("new", "waxing_crescent", "first_quarter", "waxing_gibbous", "full", "waning_gibbous", "last_quarter", "waning_crescent")
    result["moon_phase"] = names[int(fraction * 8 + .5) % 8]
    result["moon_illumination"] = round(ephem.Moon(moment).phase)
    result["moon_estimated"] = True
    for key, calc in (("next_full_moon", ephem.next_full_moon), ("next_new_moon", ephem.next_new_moon)):
        result[key] = calc(moment).datetime().replace(tzinfo=timezone.utc).astimezone(zone).isoformat()
    return result


async def async_ephemeris(hass, runtime):
    """One successful download per date; failed requests retry after one hour."""
    config = runtime["config"]
    sky = astronomy(hass, config)
    if not config.get("ephemeride_enabled", True):
        return {**sky, "almanac": None, "almanac_status": "disabled"}
    async with runtime.setdefault("ephemeris_lock", asyncio.Lock()):
        cache = runtime.get("almanac_cache")
        if cache and cache["date"] == sky["date"]:
            return {**sky, "almanac": cache, "almanac_status": "ok"}
        loop = asyncio.get_running_loop()
        if loop.time() < runtime.get("almanac_retry", 0):
            return {**sky, "almanac": None, "almanac_status": "unavailable"}
        runtime["almanac_retry"] = loop.time() + 3600
        try:
            session = async_get_clientsession(hass)
            async with session.get(SOURCE, timeout=aiohttp.ClientTimeout(total=15),
                                   headers={"User-Agent": "Station-Meteo/0.8.0 (Home Assistant; daily almanac)"}) as response:
                response.raise_for_status()
                chunks = []
                size = 0
                async for chunk in response.content.iter_chunked(32768):
                    size += len(chunk)
                    if size > 512 * 1024:
                        raise ValueError("Almanac response too large")
                    chunks.append(chunk)
                body = b"".join(chunks)
                html = body.decode(response.charset or "utf-8")
            cache = parse_almanac(html, datetime.fromisoformat(sky["date"]).date())
            runtime["almanac_cache"] = cache
            return {**sky, "almanac": cache, "almanac_status": "ok"}
        except (aiohttp.ClientError, TimeoutError, ValueError, UnicodeError):
            return {**sky, "almanac": None, "almanac_status": "unavailable"}
