"""Server-side opt-in alerts, independent of open dashboard tabs."""
from collections import deque
from datetime import timedelta
import json
import logging
import math
from pathlib import Path
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util
from .const import DEFAULT_NOTIFICATIONS
from .forecast import async_forecasts

_LOGGER = logging.getLogger(__name__)
STORM = {"lightning", "lightning-rainy"}


def pressure_delta(samples, now):
    """Require a full three-hour baseline and recent samples without long gaps."""
    if len(samples) < 2 or now - samples[-1][0] > 300:
        return None
    target = now - 10800
    baseline = min(samples, key=lambda p: abs(p[0] - target))
    if abs(baseline[0] - target) > 120:
        return None
    window = [p for p in samples if p[0] >= baseline[0]]
    if any(b[0] - a[0] > 600 for a, b in zip(window, window[1:])):
        return None
    return samples[-1][1] - baseline[1]


class NotificationManager:
    def __init__(self, hass, runtime):
        self.hass, self.runtime = hass, runtime
        self.samples = deque(maxlen=200)
        self.pressure_entity = None
        self.latched = set()
        self.sent = {}
        self.forecast = []
        self.forecast_at = 0
        self.forecast_entity = None
        self._cancel = None
        self._busy = False
        self.dictionaries = {lang: json.loads((Path(__file__).parent / "frontend" / "i18n" / f"{lang}.json").read_text()) for lang in ("fr", "en", "es")}

    def start(self):
        self._cancel = async_track_time_interval(self.hass, self.check, timedelta(minutes=1))

    def stop(self):
        if self._cancel:
            self._cancel()
            self._cancel = None

    def state(self, role):
        eid = self.runtime["config"].get("entities", {}).get(role)
        s = self.hass.states.get(eid) if eid else None
        return s if s and s.state not in ("unknown", "unavailable", "") else None

    def value(self, role):
        state = self.state(role)
        if state is None:
            return None
        try:
            v = float(state.state)
        except ValueError:
            return None
        if not math.isfinite(v):
            return None
        u = str(state.attributes.get("unit_of_measurement", "")).lower()
        if role == "pressure":
            return v * {"pa": .01, "kpa": 10, "inhg": 33.8638866667, "mmhg": 1.3332239}.get(u, 1)
        if role == "wind_gust":
            return v * {"m/s": 3.6, "mph": 1.609344, "kn": 1.852, "kt": 1.852, "knots": 1.852}.get(u, 1)
        return v

    async def check(self, now):
        if self._busy:
            return
        self._busy = True
        try:
            await self._check(now.timestamp())
        finally:
            self._busy = False

    async def _check(self, now):
        cfg = self.runtime["config"]
        opts = {**DEFAULT_NOTIFICATIONS, **cfg.get("notifications", {})}
        eid = cfg.get("entities", {}).get("pressure")
        if eid != self.pressure_entity:
            self.samples.clear()
            self.pressure_entity = eid
        p = self.value("pressure")
        if p is not None:
            self.samples.append((now, p))
        else:
            self.samples.clear()
        if not opts["enabled"] or not opts["recipients"]:
            self.latched.clear()
            return
        w = self.state("weather") or self.state("weather_fallback")
        wid = tuple(cfg.get("entities", {}).get(role) for role in ("weather", "weather_fallback"))
        if wid != self.forecast_entity:
            self.forecast, self.forecast_at, self.forecast_entity = [], 0, wid
        if opts["storm"] and w and now - self.forecast_at >= 600:
            self.forecast_at = now
            result = await async_forecasts(self.hass, cfg, now=now, kinds=("hourly",))
            self.forecast = result["hourly"]
        forecast_storm = False
        if w and now - self.forecast_at <= 1200:
            for f in self.forecast:
                dt = dt_util.parse_datetime(f.get("datetime", ""))
                if dt and now <= dt.timestamp() <= now + 10800 and f.get("condition") in STORM:
                    forecast_storm = True
                    break
        delta = pressure_delta(self.samples, now)
        gust = self.value("wind_gust")
        rain = self.state("rain_status")
        alerts = {
            "pressure": opts["pressure"] and delta is not None and delta <= -opts["pressure_drop"],
            "rain": opts["rain"] and rain is not None and rain.state.lower() in ("on", "wet", "raining", "true"),
            "gust": opts["gust"] and gust is not None and gust >= opts["gust_threshold"],
            "storm": opts["storm"] and w is not None and (w.state in STORM or forecast_storm),
        }
        lang = cfg.get("language", "auto")
        if lang == "auto":
            lang = getattr(self.hass.config, "language", "fr")[:2]
        dictionary = self.dictionaries.get(lang, self.dictionaries["en"])
        for key, active in alerts.items():
            if not active:
                self.latched.discard(key)
                continue
            if key in self.latched or now - self.sent.get(key, -math.inf) < opts["cooldown"] * 60:
                continue
            values = {"drop": f"{abs(delta or 0):.1f}", "gust": f"{gust or 0:.1f}"}
            message = dictionary[f"alert_{key}"].format(**values)
            succeeded = False
            for target in opts["recipients"]:
                domain, service = target.split(".", 1)
                data = {"title": f"Station Météo — {cfg['location']}", "message": message}
                if domain == "persistent_notification":
                    data["notification_id"] = f"station_meteo_{key}"
                try:
                    await self.hass.services.async_call(domain, service, data, blocking=True)
                    succeeded = True
                except HomeAssistantError:
                    _LOGGER.warning("Failed to send weather notification to %s", target, exc_info=True)
            if succeeded:
                self.latched.add(key)
                self.sent[key] = now
