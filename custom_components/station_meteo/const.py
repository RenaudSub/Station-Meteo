"""Station Météo constants."""
DOMAIN = "station_meteo"
VERSION = "1.3.0"
WEATHER_CONDITIONS = ("sunny", "clear-night", "partlycloudy", "cloudy", "rainy", "pouring", "snowy", "snowy-rainy", "lightning", "lightning-rainy", "fog", "windy", "windy-variant", "hail", "exceptional")
PANEL_PATH = "station-meteo"
ROLES = ("temperature", "humidity", "pressure", "illuminance", "irradiance", "uv", "wind_speed", "wind_gust", "wind_direction", "rain_total", "rain_rate", "rain_status", "dew_point", "battery", "signal", "weather", "weather_fallback", "bulletin", "weather_alert")
DEFAULT_NOTIFICATIONS = {
    "enabled": False, "recipients": [], "pressure": True, "pressure_drop": 3,
    "rain": True, "gust": False, "gust_threshold": 60, "storm": True, "cooldown": 60,
}
DEFAULT_MAP_BUTTONS = [
    {"id": "lightning", "name": "", "enabled": True, "mode": "meteociel", "url": "https://www.meteociel.fr/observations-meteo/foudre-direct.php?x=21246.45&y=35533.4&zoom=5.9", "latitude": None, "longitude": None, "zoom": 4},
    {"id": "radar", "name": "", "enabled": True, "mode": "meteociel", "url": "https://www.meteociel.fr/observations-meteo/radar2.php?region=so&mode=1", "latitude": None, "longitude": None, "zoom": 4},
    {"id": "satellite", "name": "", "enabled": True, "mode": "meteociel", "url": "https://www.meteociel.fr/observations-meteo/satellite.php?region=fr&mode=animation-visible-composition-mtg", "latitude": None, "longitude": None, "zoom": 4},
    {"id": "humidity", "name": "", "enabled": True, "mode": "meteociel", "url": "https://www.meteociel.fr/observations-meteo/humi.php?region=r8", "latitude": None, "longitude": None, "zoom": 4},
    {"id": "rain24", "name": "", "enabled": True, "mode": "meteociel", "url": "https://www.meteociel.fr/observations-meteo/rr.php?region=r8", "latitude": None, "longitude": None, "zoom": 4},
    {"id": "gusts", "name": "", "enabled": True, "mode": "meteociel", "url": "https://www.meteociel.fr/observations-meteo/vent-rafales.php?region=r8&mode=0", "latitude": None, "longitude": None, "zoom": 4},
    {"id": "precipitation", "name": "", "enabled": True, "mode": "meteociel", "url": "https://www.meteociel.fr/observations-meteo/radarzoom.php?x=6637.38&y=10025.69&ech=6&zoom=3.9", "latitude": None, "longitude": None, "zoom": 4},
    {"id": "cumuls", "name": "", "enabled": True, "mode": "meteociel", "url": "https://www.meteociel.fr/observations-meteo/radarzoom.php?x=5764.4&y=9054.2&ech=3&zoom=2.5&lame=1", "latitude": None, "longitude": None, "zoom": 4},
]
DEFAULT_CONFIG = {
    "map_buttons": DEFAULT_MAP_BUTTONS,
    "latitude": None, "longitude": None, "ephemeride_enabled": True,
    "compass_url": "", "arrow_url": "", "weather_icons": {}, "background_url": "", "location": "Casefabre", "altitude": 247, "language": "auto",
    "wind_unit": "km/h", "pressure_mode": "absolute", "lux_factor": 126.7,
    "notifications": DEFAULT_NOTIFICATIONS, "estimate_irradiance": False, "entities": {}, "device_id": "",
}


def normalize_map_buttons(cards):
    """Upgrade unchanged old defaults; preserve every personalized target/mode."""
    saved_cards = cards if isinstance(cards, list) else []
    by_id = {card.get("id"): card for card in saved_cards if isinstance(card, dict) and card.get("id")}
    result = []
    for i, default in enumerate(DEFAULT_MAP_BUTTONS):
        saved = by_id.get(default["id"], {})
        if not saved and i < len(saved_cards) and isinstance(saved_cards[i], dict) and not saved_cards[i].get("id"):
            saved = saved_cards[i]
        card = {**default, **saved}
        if default["id"] == "radar" and card["url"] == "https://www.meteociel.fr/observations-meteo/radarzoom.php?x=6742.28&y=9941.72&ech=11&zoom=4" and card["mode"] in ("iframe", "meteociel"):
            card.update(url=default["url"], mode=default["mode"])
        if i < 2 and card["mode"] == "iframe" and card["url"] == default["url"]:
            card["mode"] = "meteociel"
        if i == 2 and card["mode"] == "satellite" and card["url"] == "https://view.eumetsat.int/" and card["latitude"] is None and card["longitude"] is None and card["zoom"] == 4:
            card.update(mode=default["mode"], url=default["url"])
        result.append(card)
    if isinstance(cards, list):
        result.extend(dict(card) for card in cards if isinstance(card, dict) and str(card.get("id", "")).startswith("custom"))
    return result
