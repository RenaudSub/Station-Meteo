"""Editable local almanac calendars, kept outside the integration directory."""
import asyncio
from calendar import monthrange
from copy import deepcopy
from hashlib import sha256
import json
import logging
import os
from pathlib import Path
import tempfile

_LOGGER = logging.getLogger(__name__)
KINDS = ("saints", "citations", "dictons")
DEFAULT_DIRECTORY = Path(__file__).parent / "almanac"
DATE_KEYS = {f"{m:02}-{d:02}" for m in range(1, 13) for d in range(1, monthrange(2000, m)[1] + 1)}
MAX_BYTES = 256 * 1024


def validate_calendar(kind, entries):
    """Require one entry per calendar date, including February 29."""
    if kind not in KINDS or not isinstance(entries, dict) or set(entries) != DATE_KEYS:
        raise ValueError("A complete calendar of 366 dates (MM-DD) is required")
    result = {}
    def text(value, maximum, empty=False):
        if not isinstance(value, str) or len(value) > maximum or any(ord(c) < 32 and c not in '\n\t' for c in value):
            raise ValueError("Invalid almanac text")
        value = value.strip()
        if not empty and not value:
            raise ValueError("Almanac text cannot be empty")
        return value
    for key in sorted(DATE_KEYS):
        value = entries[key]
        if kind == "citations":
            if not isinstance(value, dict) or set(value) != {"text", "author"}:
                raise ValueError(f"Invalid quote at {key}: text and author fields required")
            result[key] = {"text": text(value["text"], 600), "author": text(value["author"], 120, True)}
        else:
            result[key] = text(value, 600)
    return result


def decode_calendar(kind, content):
    if len(content) > MAX_BYTES:
        raise ValueError("Almanac file too large")
    return validate_calendar(kind, json.loads(content.decode("utf-8-sig")))


def encoded(entries):
    return (json.dumps(entries, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


class LocalAlmanac:
    """Three JSON files, atomic saves and revision guards against lost edits."""
    def __init__(self, directory, defaults=DEFAULT_DIRECTORY):
        self.directory = Path(directory)
        self.defaults_directory = Path(defaults)
        self.lock = asyncio.Lock()
        self.defaults = {}
        self._warned = {}

    def initialize(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        for kind in KINDS:
            self.defaults[kind] = decode_calendar(kind, (self.defaults_directory / f"{kind}.json").read_bytes())
            path = self.directory / f"{kind}.json"
            if not path.exists():
                self._write(path, encoded(self.defaults[kind]))

    def _write(self, path, content):
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.directory, prefix='.almanac-', suffix='.tmp', delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(content)
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def read(self, kind):
        if kind not in KINDS:
            raise ValueError("Unknown almanac calendar")
        path = self.directory / f"{kind}.json"
        try:
            with path.open('rb') as stream:
                content = stream.read(MAX_BYTES + 1)
        except OSError:
            content = b''
        revision = sha256(content).hexdigest()
        try:
            entries = decode_calendar(kind, content)
            warning = False
        except (ValueError, UnicodeError):
            entries = deepcopy(self.defaults[kind])
            warning = True
            if self._warned.get(kind) != revision:
                _LOGGER.warning("Invalid or missing local %s calendar; bundled defaults are used without replacing the customized file", kind)
                self._warned[kind] = revision
        return {"entries": entries, "revision": revision, "warning": warning}

    def editors(self):
        return {kind: {**self.read(kind), "defaults": deepcopy(self.defaults[kind])} for kind in ("citations", "dictons")}

    def save(self, kind, entries, expected_revision):
        if kind not in ("citations", "dictons"):
            raise ValueError("This calendar has no editor")
        entries = validate_calendar(kind, entries)
        current = self.read(kind)
        if current["revision"] != expected_revision:
            raise ValueError("almanac_conflict")
        self._write(self.directory / f"{kind}.json", encoded(entries))
        return self.read(kind)

    def daily(self, day):
        key = day.strftime('%m-%d')
        calendars = {kind: self.read(kind) for kind in KINDS}
        quote = calendars['citations']['entries'][key]
        return {"date": day.isoformat(), "saint": calendars['saints']['entries'][key],
                "quote": quote['text'], "quote_author": quote['author'],
                "saying": calendars['dictons']['entries'][key], "local": True,
                "fallback": any(value['warning'] for value in calendars.values())}
