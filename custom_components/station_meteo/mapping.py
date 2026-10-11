"""Language-independent WS90 entity mapping; no entity renames."""
import re

DIRECT = {
    "temperature": "temperature", "humidity": "humidity", "pressure": "pressure",
    "illuminance": "illuminance", "battery": "battery", "signal_strength": "signal",
    "dew_point": "dew_point", "direction": "wind_direction", "uv_index": "uv",
    "precipitation": "rain_total", "irradiance": "irradiance",
}

def map_entities(entities):
    """Map registry metadata, not translated display names or changing values."""
    result = {}
    unmapped = []
    for entity in entities:
        eid = entity["entity_id"]
        domain = eid.split(".")[0]
        key = entity.get("translation_key") or ""
        dc = entity.get("device_class") or ""
        uid = entity.get("unique_id", "").lower()
        role = None
        if domain == "binary_sensor" and (dc == "moisture" or key in ("moisture", "rain")):
            role = "rain_status"
        elif domain == "sensor":
            if dc in ("wind_speed", "speed") or "speed_" in uid:
                # bthome-ble numbers duplicate measurement keys from 1: speed_1, speed_2.
                match = re.search(r"(?:^|-)speed_(\d+)(?:-|$)", uid)
                if match:
                    role = "wind_speed" if int(match[1]) == 1 else "wind_gust" if int(match[1]) == 2 else None
                else:
                    unmapped.append(eid)
                    continue
            else:
                role = DIRECT.get(key) or DIRECT.get(dc)
                if not role:
                    for token in ("dew_point", "direction", "uv_index", "precipitation"):
                        if token in uid:
                            role = DIRECT[token]
                            break
        if role and not entity.get("disabled"):
            if role in result:
                unmapped.append(eid)
            else:
                result[role] = eid
    return result, unmapped
