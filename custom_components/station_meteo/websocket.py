"""Authenticated panel settings and BTHome device discovery."""
import math
import re
import sqlite3
from urllib.parse import urlsplit, unquote
import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from .const import DOMAIN, ROLES, WEATHER_CONDITIONS, DEFAULT_CONFIG, DEFAULT_NOTIFICATIONS, DEFAULT_MAP_BUTTONS
from .mapping import map_entities
from .forecast import async_forecasts
from .ephemeris import async_ephemeris
from .satellite import async_satellite
from .meteociel import async_meteociel, source_spec


def catalog(hass):
    registry = er.async_get(hass)
    devices = dr.async_get(hass)
    result = []
    bthome_devices = {device.id: device for entry in hass.config_entries.async_entries("bthome")
                      for device in dr.async_entries_for_config_entry(devices, entry.entry_id)}
    for device in bthome_devices.values():
        entities = er.async_entries_for_device(registry, device.id, include_disabled_entities=True)
        if not any(e.platform == "bthome" for e in entities):
            continue
        mapped_entities = []
        for e in entities:
            if e.platform != "bthome":
                continue
            state = hass.states.get(e.entity_id)
            mapped_entities.append({
                "entity_id": e.entity_id, "unique_id": e.unique_id,
                "translation_key": e.translation_key,
                "device_class": e.device_class or e.original_device_class or (state.attributes.get("device_class") if state else None),
                "disabled": e.disabled_by is not None,
            })
        mapping, ambiguous = map_entities(mapped_entities)
        result.append({"id": device.id, "name": device.name_by_user or device.name or device.id,
                       "original_name": device.name, "model": device.model,
                       "identifiers": sorted(list(device.identifiers)),
                       "mapping": mapping, "ambiguous": ambiguous,
                       "disabled": [e["entity_id"] for e in mapped_entities if e["disabled"]]})
    return result


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/config"})
@websocket_api.async_response
async def ws_config(hass, connection, msg):
    runtime = hass.data.get(DOMAIN, {})
    if not runtime.get("loaded"):
        connection.send_error(msg["id"], "not_loaded", "Station Météo is not loaded")
        return
    connection.send_result(msg["id"], runtime["config"])


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/catalog"})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_catalog(hass, connection, msg):
    connection.send_result(msg["id"], catalog(hass))


def validate_image_url(url):
    if not isinstance(url, str) or len(url) > 2048 or any(ord(c) < 32 for c in url):
        raise ValueError("Invalid image URL")
    if url:
        parsed = urlsplit(url)
        external = parsed.scheme == "https" and parsed.netloc and not parsed.username and not parsed.password
        local = url.startswith(("/local/", "/station_meteo/images/", "/station_meteo/frontend/")) and not parsed.netloc and ".." not in unquote(parsed.path).split("/")
        if not (external or local):
            raise ValueError("Use an HTTPS image URL or a supported local image path")


def validate_config(hass, data):
    """Reject invalid types, unknown roles and mismatched entity domains."""
    if set(data) - set(DEFAULT_CONFIG):
        raise ValueError("Unknown setting")
    result = {**DEFAULT_CONFIG, **data}
    for field in ("location", "device_id"):
        if not isinstance(result[field], str) or len(result[field]) > 200:
            raise ValueError(f"Invalid {field}")
    validate_image_url(result["background_url"])
    validate_image_url(result["compass_url"])
    validate_image_url(result["arrow_url"])
    icons = result["weather_icons"]
    if not isinstance(icons, dict) or set(icons) - set(WEATHER_CONDITIONS):
        raise ValueError("Invalid weather icons")
    for url in icons.values():
        validate_image_url(url)
    if result["language"] not in ("auto", "fr", "en", "es"):
        raise ValueError("Invalid language")
    if result["theme"] not in ("light", "dark", "auto", "schedule"):
        raise ValueError("Invalid theme")
    for key in ("theme_dark_start", "theme_dark_end"):
        if not isinstance(result[key], str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", result[key]):
            raise ValueError(f"Invalid {key}")
    if result["theme"] == "schedule" and result["theme_dark_start"] == result["theme_dark_end"]:
        raise ValueError("Dark start and end must differ")
    if result["wind_unit"] not in ("km/h", "m/s"):
        raise ValueError("Invalid wind unit")
    if result["pressure_mode"] not in ("absolute", "sea_level"):
        raise ValueError("Invalid pressure mode")
    for name, lo, hi in (("altitude", -500, 9000), ("lux_factor", 1, 1000)):
        value = result[name]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not lo <= value <= hi:
            raise ValueError(f"Invalid {name}")
    for field, bound in (("latitude", 90), ("longitude", 180)):
        value = result[field]
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not -bound <= value <= bound):
            raise ValueError(f"Invalid {field}")
    if not isinstance(result["ephemeride_enabled"], bool):
        raise ValueError("Invalid ephemeride_enabled")
    if not isinstance(result["estimate_irradiance"], bool):
        raise ValueError("Invalid estimate_irradiance")
    if not isinstance(result["entities"], dict) or set(result["entities"]) - set(ROLES):
        raise ValueError("Invalid entity roles")
    opts = result["notifications"]
    if not isinstance(opts, dict) or set(opts) - set(DEFAULT_NOTIFICATIONS):
        raise ValueError("Invalid notifications")
    opts = {**DEFAULT_NOTIFICATIONS, **opts}
    for key in ("enabled", "pressure", "rain", "gust", "storm", "vigilance"):
        if not isinstance(opts[key], bool):
            raise ValueError(f"Invalid notification {key}")
    for key, lo, hi in (("pressure_drop", 0.5, 20), ("gust_threshold", 1, 250), ("cooldown", 5, 1440)):
        v = opts[key]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not lo <= v <= hi:
            raise ValueError(f"Invalid notification {key}")
    recipients = opts["recipients"]
    if not isinstance(recipients, list) or len(recipients) > 20 or any(not isinstance(v, str) for v in recipients):
        raise ValueError("Invalid notification recipients")
    allowed = notification_targets(hass)
    if any(v not in allowed for v in recipients):
        raise ValueError("Unknown notification recipient")
    opts["recipients"] = list(dict.fromkeys(recipients))
    result["notifications"] = opts
    cards = result["map_buttons"]
    if not isinstance(cards, list) or not len(DEFAULT_MAP_BUTTONS) <= len(cards) <= len(DEFAULT_MAP_BUTTONS) + 5:
        raise ValueError("Expected all built-in buttons and at most five custom buttons")
    normalized = []
    custom_ids = set()
    for index, card in enumerate(cards):
        custom = index >= len(DEFAULT_MAP_BUTTONS)
        if custom:
            identity = card.get("id") if isinstance(card, dict) else None
            if identity not in {f"custom{i}" for i in range(1, 6)} or identity in custom_ids:
                raise ValueError("Invalid custom map identity")
            custom_ids.add(identity)
            default = {**DEFAULT_MAP_BUTTONS[0], "id": identity, "name": "", "mode": "iframe"}
        else:
            default = DEFAULT_MAP_BUTTONS[index]
        if not isinstance(card, dict) or set(card) - set(default):
            raise ValueError("Invalid map button")
        card = {**default, **card}
        if card["id"] != default["id"] or not isinstance(card["enabled"], bool):
            raise ValueError("Invalid map identity or visibility")
        if not isinstance(card["name"], str) or len(card["name"]) > 60:
            raise ValueError("Invalid map name")
        if card["mode"] not in ("iframe", "tab", "satellite", "meteociel"):
            raise ValueError("Invalid map mode")
        url = card["url"]
        if not isinstance(url, str) or len(url) > 2048 or any(ord(c) < 32 for c in url):
            raise ValueError("Invalid map URL")
        parsed = urlsplit(url)
        if not (parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password):
            raise ValueError("Map URLs must use HTTPS")
        if card["mode"] == "meteociel":
            try:
                source_spec(url)
            except ValueError as err:
                raise ValueError(f"native_map_unsupported: {card['name'] or card['id']}") from err
        for field, bound in (("latitude", 90), ("longitude", 180)):
            value = card[field]
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not -bound <= value <= bound):
                raise ValueError("Invalid satellite coordinates")
        zoom = card["zoom"]
        if isinstance(zoom, bool) or not isinstance(zoom, (int, float)) or not math.isfinite(zoom) or not 2 <= zoom <= 8:
            raise ValueError("Invalid satellite zoom")
        normalized.append(card)
    result["map_buttons"] = normalized
    registry = er.async_get(hass)
    for role, eid in result["entities"].items():
        if not isinstance(eid, str):
            raise ValueError("Invalid entity")
        if not eid:
            continue
        domains = ("weather",) if role in ("weather", "weather_fallback") else ("sensor", "input_text") if role == "bulletin" else ("binary_sensor", "sensor") if role == "rain_status" else ("sensor",)
        if eid.split(".")[0] not in domains:
            raise ValueError(f"Invalid domain for {role}")
        if not registry.async_get(eid) and not hass.states.get(eid):
            raise ValueError(f"Entity does not exist: {eid}")
    return result


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/save", vol.Required("config"): dict})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_save(hass, connection, msg):
    runtime = hass.data.get(DOMAIN, {})
    if not runtime.get("loaded"):
        connection.send_error(msg["id"], "not_loaded", "Station Météo is not loaded")
        return
    try:
        data = validate_config(hass, msg["config"])
        async with runtime["lock"]:
            await runtime["store"].async_save(data)
            if runtime.get("archive"):
                from datetime import datetime, timezone
                runtime["archive"].sample(datetime.now(timezone.utc).timestamp())
                await runtime["archive"].drain(True)
            runtime["config"] = data
        if runtime.get("archive"):
            await runtime["archive"].reconfigure()
    except (ValueError, OSError, sqlite3.Error) as err:
        connection.send_error(msg["id"], "invalid_config", str(err))
        return
    connection.send_result(msg["id"], data)


def notification_targets(hass):
    """Only existing user-selectable notification actions."""
    targets = ["persistent_notification.create"]
    targets.extend(f"notify.{name}" for name in hass.services.async_services().get("notify", {}) if name != "send_message")
    return sorted(targets)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/notification_targets"})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_notification_targets(hass, connection, msg):
    connection.send_result(msg["id"], notification_targets(hass))


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/entity_exclusions"})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_entity_exclusions(hass, connection, msg):
    registry = er.async_get(hass)
    connection.send_result(msg["id"], [entry.entity_id for entry in registry.entities.values() if entry.platform == "adguard"])


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/forecast"})
@websocket_api.async_response
async def ws_forecast(hass, connection, msg):
    runtime = hass.data.get(DOMAIN, {})
    if not runtime.get("loaded"):
        connection.send_error(msg["id"], "not_loaded", "Station Météo is not loaded")
        return
    connection.send_result(msg["id"], await async_forecasts(hass, runtime["config"]))


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/ephemeris"})
@websocket_api.async_response
async def ws_ephemeris(hass, connection, msg):
    runtime = hass.data.get(DOMAIN, {})
    if not runtime.get("loaded"):
        connection.send_error(msg["id"], "not_loaded", "Station Météo is not loaded")
        return
    connection.send_result(msg["id"], await async_ephemeris(hass, runtime))


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/satellite", vol.Required("index"): vol.All(int, vol.Range(min=0, max=len(DEFAULT_MAP_BUTTONS)+4))})
@websocket_api.async_response
async def ws_satellite(hass, connection, msg):
    runtime = hass.data.get(DOMAIN, {})
    if not runtime.get("loaded"):
        connection.send_error(msg["id"], "not_loaded", "Station Météo is not loaded")
        return
    connection.send_result(msg["id"], await async_satellite(hass, runtime, msg["index"]))


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/meteociel", vol.Required("index"): vol.All(int, vol.Range(min=0, max=len(DEFAULT_MAP_BUTTONS)+4)), vol.Optional("product"): vol.In([1, 2, 3, 4, 5, 6, 7, 15]), vol.Optional("viewport"): {vol.Required("x"): vol.Coerce(float), vol.Required("y"): vol.Coerce(float), vol.Required("zoom"): vol.Coerce(float)}, vol.Optional("options"): {vol.Optional("duration"): vol.In([2, 5, 10, 30, 60, 120]), vol.Optional("cities"): vol.In([0, 1, 2, 3]), vol.Optional("roads"): bool, vol.Optional("rivers"): bool, vol.Optional("relief"): bool}})
@websocket_api.async_response
async def ws_meteociel(hass, connection, msg):
    runtime = hass.data.get(DOMAIN, {})
    if not runtime.get("loaded"):
        connection.send_error(msg["id"], "not_loaded", "Station Météo is not loaded")
        return
    connection.send_result(msg["id"], await async_meteociel(hass, runtime, msg["index"], msg.get("options"), msg.get("viewport"), msg.get("product")))


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/almanac"})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_almanac(hass, connection, msg):
    runtime = hass.data.get(DOMAIN, {})
    if not runtime.get("loaded"):
        connection.send_error(msg["id"], "not_loaded", "Station Météo is not loaded")
        return
    service = runtime["almanac"]
    try:
        async with service.lock:
            result = await hass.async_add_executor_job(service.editors)
        connection.send_result(msg["id"], result)
    except (OSError, ValueError):
        connection.send_error(msg["id"], "almanac_unavailable", "Local almanac files are unavailable")


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/almanac_save",
    vol.Required("kind"): vol.In(("citations", "dictons")), vol.Required("entries"): dict,
    vol.Required("revision"): vol.Match(r"^[a-f0-9]{64}$")})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_almanac_save(hass, connection, msg):
    runtime = hass.data.get(DOMAIN, {})
    if not runtime.get("loaded"):
        connection.send_error(msg["id"], "not_loaded", "Station Météo is not loaded")
        return
    service = runtime["almanac"]
    try:
        async with service.lock:
            result = await hass.async_add_executor_job(service.save, msg["kind"], msg["entries"], msg["revision"])
        connection.send_result(msg["id"], result)
    except (OSError, ValueError) as err:
        conflict = str(err) == "almanac_conflict"
        connection.send_error(msg["id"], "almanac_conflict" if conflict else "invalid_almanac", "almanac_conflict" if conflict else "Invalid calendar or local file could not be saved")


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/history", vol.Required("role"): vol.In(('rain', 'temperature', 'humidity', 'uv', 'irradiance', 'pressure', 'wind_speed')), vol.Required("date"): str, vol.Required("scale"): vol.In(('hour', 'week', 'month'))})
@websocket_api.async_response
async def ws_history(hass, connection, msg):
    from datetime import date
    import sqlite3
    runtime = hass.data.get(DOMAIN, {})
    if not runtime.get("loaded") or "archive" not in runtime:
        connection.send_error(msg["id"], "not_loaded", "Station Météo is not loaded")
        return
    try:
        day = date.fromisoformat(msg["date"])
        if day.isoformat() != msg["date"]:
            raise ValueError("Invalid date")
        result = await runtime["archive"].query(msg["role"], day, msg["scale"])
        connection.send_result(msg["id"], result)
    except (ValueError, OSError, sqlite3.Error) as err:
        connection.send_error(msg["id"], "history_unavailable", str(err))


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/vigilance"})
@websocket_api.async_response
async def ws_vigilance(hass, connection, msg):
    from .vigilance import current_alerts
    runtime = hass.data.get(DOMAIN, {})
    if not runtime.get("loaded"):
        connection.send_error(msg["id"], "not_loaded", "Station Météo is not loaded")
        return
    connection.send_result(msg["id"], current_alerts(hass, runtime))


@callback
def async_register_commands(hass: HomeAssistant):
    for command in (ws_vigilance, ws_history, ws_almanac, ws_almanac_save, ws_config, ws_catalog, ws_save, ws_forecast, ws_ephemeris, ws_satellite, ws_meteociel, ws_notification_targets, ws_entity_exclusions):
        websocket_api.async_register_command(hass, command)
