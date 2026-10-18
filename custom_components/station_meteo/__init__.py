"""Local weather station panel for Home Assistant."""
from pathlib import Path
import asyncio
from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.storage import Store
from .const import DOMAIN, DEFAULT_CONFIG, VERSION, PANEL_PATH, normalize_map_buttons
from .websocket import async_register_commands
from .notifications import NotificationManager
from .image_upload import ImageUploadView
from .almanac_data import LocalAlmanac
from .archive import ArchiveService

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Load the integration."""
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Expose the static panel and persisted settings."""
    runtime = hass.data.setdefault(DOMAIN, {})
    if "store" not in runtime:
        store = Store(hass, 1, f"{DOMAIN}.settings")
        saved = await store.async_load() or {}
        runtime.update(store=store, config={**DEFAULT_CONFIG, **saved}, lock=asyncio.Lock())
        runtime["config"]["map_buttons"] = normalize_map_buttons(saved.get("map_buttons"))
    if "almanac" not in runtime:
        service = LocalAlmanac(hass.config.path(DOMAIN, "almanac"))
        await hass.async_add_executor_job(service.initialize)
        runtime["almanac"] = service
    if not runtime.get("registered"):
        image_directory = Path(hass.config.path(DOMAIN, "images"))
        await hass.async_add_executor_job(image_directory.mkdir, 0o755, True, True)
        await hass.http.async_register_static_paths([
            StaticPathConfig(f"/{DOMAIN}/frontend", str(Path(__file__).parent / "frontend"), False),
            StaticPathConfig(f"/{DOMAIN}/images", str(image_directory), False)
        ])
        hass.http.register_view(ImageUploadView(hass, image_directory))
        async_register_commands(hass)
        runtime["registered"] = True
    await panel_custom.async_register_panel(
        hass, frontend_url_path=PANEL_PATH, webcomponent_name="station-meteo-panel",
        sidebar_title="Station Météo", sidebar_icon="mdi:weather-partly-cloudy",
        module_url=f"/{DOMAIN}/frontend/station-meteo.js?v={VERSION}&build=4",
        require_admin=False, config={"version": VERSION},
    )
    runtime["notifications_manager"] = NotificationManager(hass, runtime)
    runtime["notifications_manager"].start()
    runtime["archive"] = ArchiveService(hass, runtime)
    await runtime["archive"].start()
    runtime["loaded"] = True
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Remove the panel, retaining settings for later reload."""
    await hass.data[DOMAIN]["archive"].stop()
    hass.data[DOMAIN]["notifications_manager"].stop()
    frontend.async_remove_panel(hass, PANEL_PATH)
    hass.data[DOMAIN]["loaded"] = False
    return True
