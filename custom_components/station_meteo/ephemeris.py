"""Local observer astronomy and offline editable daily almanac."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from astral import Observer
import ephem
from astral.sun import sunrise, sunset, noon


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
    """No network: calendar dates follow Home Assistant's configured timezone."""
    sky = astronomy(hass, runtime["config"])
    if not runtime["config"].get("ephemeride_enabled", True):
        return {**sky, "almanac": None, "almanac_status": "disabled"}
    service = runtime["almanac"]
    async with service.lock:
        data = await hass.async_add_executor_job(service.daily, datetime.fromisoformat(sky["date"]).date())
    return {**sky, "almanac": data, "almanac_status": "ok"}
