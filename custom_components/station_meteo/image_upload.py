"""Authenticated image upload, persisted outside the integration code directory."""
import base64
import binascii
import math
import re
import xml.etree.ElementTree as ET
from io import BytesIO
from pathlib import Path
from uuid import uuid4
from PIL import Image, UnidentifiedImageError
from homeassistant.components.http import HomeAssistantView, KEY_HASS_USER
from .const import DOMAIN

MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000


def validate_svg(data: bytes) -> None:
    """Accept standalone vector artwork, without active or external content."""
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise ValueError("SVG declarations are not supported")
    try:
        root = ET.fromstring(data)
    except ET.ParseError as err:
        raise ValueError("Invalid SVG") from err
    namespace = "{http://www.w3.org/2000/svg}"
    tags = {"svg", "title", "desc", "defs", "g", "path", "circle", "ellipse", "rect", "line", "polyline", "polygon",
            "linearGradient", "radialGradient", "stop", "filter", "feGaussianBlur", "feOffset", "feComponentTransfer",
            "feFuncA", "feFuncR", "feFuncG", "feFuncB", "feMerge", "feMergeNode", "feColorMatrix", "feBlend",
            "feComposite", "clipPath", "mask"}
    if root.tag != namespace + "svg":
        raise ValueError("Expected an SVG document")
    try:
        box = [float(v) for v in re.split(r"[ ,]+", root.attrib.get("viewBox", "").strip())]
        if len(box) != 4 or not all(math.isfinite(v) for v in box) or box[2] <= 0 or box[3] <= 0:
            raise ValueError
    except ValueError as err:
        raise ValueError("SVG requires a valid viewBox") from err
    elements = list(root.iter())
    if len(elements) > 2000:
        raise ValueError("SVG is too complex")
    for node in elements:
        if not node.tag.startswith(namespace) or node.tag[len(namespace):] not in tags:
            raise ValueError("Unsupported SVG element")
        for key, value in node.attrib.items():
            if key.startswith("{") or key.lower().startswith("on") or key.lower() in {"style", "href", "src"}:
                raise ValueError("Unsupported SVG attribute")
            # Local gradient/filter references are permitted; external resources are not.
            if "url(" in value.lower() and not re.fullmatch(r"url\(#[A-Za-z_][A-Za-z0-9_.:-]*\)", value):
                raise ValueError("SVG external references are not supported")
            if re.search(r"(?:https?:|javascript:|data:|file:|@import)", value, re.IGNORECASE):
                raise ValueError("SVG external references are not supported")


def save_image(directory: Path, content: str, kind: str = "image") -> str:
    """Verify supported image bytes before storing under a generated safe name."""
    if not isinstance(content, str) or len(content) > ((MAX_IMAGE_BYTES + 2) // 3) * 4:
        raise ValueError("Image must be at most 8 MB")
    try:
        data = base64.b64decode(content, validate=True)
    except (ValueError, binascii.Error) as err:
        raise ValueError("Invalid image encoding") from err
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise ValueError("Image must be at most 8 MB")
    if kind not in ("image", "arrow"):
        raise ValueError("Invalid image kind")
    if kind == "arrow":
        validate_svg(data)
        ext = "svg"
    else:
        try:
            with Image.open(BytesIO(data)) as image:
                ext = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp", "GIF": "gif"}.get(image.format)
                if ext is None or image.width * image.height > MAX_IMAGE_PIXELS:
                    raise ValueError("Use JPG, PNG, GIF or WebP, up to 40 megapixels")
                image.verify()
        except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError) as err:
            raise ValueError("Invalid or unsupported image") from err
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}.{ext}"
    # Exclusive creation; the user-supplied filename never participates in paths.
    with (directory / filename).open("xb") as output:
        output.write(data)
    return f"/{DOMAIN}/images/{filename}"


class ImageUploadView(HomeAssistantView):
    url = f"/api/{DOMAIN}/image"
    name = f"api:{DOMAIN}:image"
    requires_auth = True

    def __init__(self, hass, directory):
        self.hass = hass
        self.directory = directory

    async def post(self, request):
        user = request.get(KEY_HASS_USER)
        if user is None or not user.is_admin:
            return self.json_message("Administrator required", 403)
        if not self.hass.data.get(DOMAIN, {}).get("loaded"):
            return self.json_message("Station Météo is not loaded", 503)
        try:
            payload = await request.json()
            if not isinstance(payload, dict):
                raise ValueError("Invalid upload")
            url = await self.hass.async_add_executor_job(save_image, self.directory, payload.get("content"), payload.get("kind", "image"))
        except (ValueError, TypeError) as err:
            return self.json_message(str(err), 400)
        except OSError:
            return self.json_message("Cannot store image", 500)
        return self.json({"url": url})
