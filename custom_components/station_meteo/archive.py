"""Durable, duration-weighted hourly observations, independent from Recorder retention."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from functools import partial
import logging
import math
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo

from homeassistant.const import EVENT_STATE_CHANGED, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_time_interval

_LOGGER = logging.getLogger(__name__)
UTC = timezone.utc
ROLES = ('rain', 'temperature', 'humidity', 'uv', 'irradiance', 'pressure', 'wind_speed', 'wind_gust')


def boundaries(day: date, zone: str):
    tz = ZoneInfo(zone)
    return (datetime.combine(day, time.min, tz).timestamp(),
            datetime.combine(day + timedelta(days=1), time.min, tz).timestamp())


def hour_start(stamp: float, zone: str):
    return datetime.fromtimestamp(stamp, ZoneInfo(zone)).replace(minute=0, second=0, microsecond=0).timestamp()


@dataclass(frozen=True)
class Source:
    role: str
    entity: str
    kind: str = 'gauge'
    factor: float = 1

    @property
    def key(self):
        return f'{self.kind}:{self.entity}:{self.factor:g}'

    def value(self, state):
        if state is None or state.state in ('unknown', 'unavailable', ''):
            return None
        try:
            value = float(state.state)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(value):
            return None
        unit = str(state.attributes.get('unit_of_measurement', '')).lower()
        if self.role == 'temperature':
            value = (value - 32) * 5 / 9 if 'f' in unit else value - 273.15 if unit == 'k' else value
        elif self.role == 'pressure':
            value *= {'pa': .01, 'kpa': 10, 'inhg': 33.8638866667, 'mmhg': 1.3332239}.get(unit, 1)
        elif self.role.startswith('wind'):
            value *= {'km/h': 1 / 3.6, 'mph': .44704, 'kn': .514444, 'kt': .514444, 'knots': .514444}.get(unit, 1)
        elif self.role == 'rain':
            value *= 25.4 if unit in ('in', 'in/h') else 1
        elif self.kind == 'lux':
            value *= 1000 if unit == 'klx' else 1
            value /= self.factor
        elif self.role == 'irradiance':
            value *= 1000 if unit.startswith('kw') else 1
        if self.role != 'temperature' and value < 0:
            return None
        return value


def sources(config):
    entities = config.get('entities', {})
    result = [Source(role, entities[role]) for role in ROLES if role != 'rain' and entities.get(role)]
    if entities.get('rain_total'):
        result.append(Source('rain', entities['rain_total'], 'counter'))
    elif entities.get('rain_rate'):
        result.append(Source('rain', entities['rain_rate'], 'rate'))
    if not entities.get('irradiance') and config.get('estimate_irradiance') and entities.get('illuminance'):
        result.append(Source('irradiance', entities['illuminance'], 'lux', float(config.get('lux_factor', 126.7))))
    return result


class HourArchive:
    """SQLite operations run only in an executor, under the service lock.

    A bucket's end watermark prevents duplicate import/replay. Imports precede
    live collection for today; old days only append missing later coverage.
    Disjoint coverage stays partial (seconds never imply an invented zero).
    """
    def __init__(self, path):
        self.path = Path(path)
        self.cache = {}
        self.dirty = set()
        self.previous = {}

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS hours (role TEXT, source TEXT, t REAL, integral REAL, seconds REAL, minimum REAL, maximum REAL, amount REAL, end REAL, counter REAL, PRIMARY KEY(role,source,t))')
            db.execute('CREATE TABLE IF NOT EXISTS imports (source TEXT, day TEXT, PRIMARY KEY(source,day))')
            db.execute('PRAGMA user_version=1')

    def bucket(self, source, stamp):
        key = (source.role, source.key, stamp)
        if key not in self.cache:
            with sqlite3.connect(self.path) as db:
                row = db.execute('SELECT integral,seconds,minimum,maximum,amount,end,counter FROM hours WHERE role=? AND source=? AND t=?', key).fetchone()
            self.cache[key] = list(row) if row else [0., 0., None, None, 0., stamp, None]
        return key, self.cache[key]

    def interval(self, source, start, end, value, amount, zone, end_value=None):
        """Append only previously unrecorded coverage; rain belongs to interval end."""
        if not end > start:
            return
        while start < end:
            stamp = hour_start(start, zone)
            stop = min(stamp + 3600, end)
            key, row = self.bucket(source, stamp)
            effective = max(start, row[5])
            if stop > effective:
                seconds = stop - effective
                row[0] += value * seconds
                row[1] += seconds
                row[2] = value if row[2] is None else min(row[2], value)
                row[3] = value if row[3] is None else max(row[3], value)
                # If part of the counter interval was already recorded, do not
                # count its entire change again. Recorder normally shares exact
                # boundaries with persisted end watermarks.
                if source.role == 'rain':
                    if source.kind == 'rate':
                        row[4] += value * seconds / 3600
                    elif stop == end:
                        if effective > start and row[6] is not None and end_value is not None:
                            row[4] += max(0, end_value - row[6]) if end_value >= row[6] else end_value
                        else:
                            row[4] += amount
                    row[6] = end_value if stop == end else value
                row[5] = stop
                self.dirty.add(key)
            start = stop

    def feed(self, source, stamp, value, zone, live=True):
        key = (source.role, source.key)
        old = self.previous.get(key)
        if old and stamp > old[0] and (not live or stamp - old[0] <= 180):
            t, previous = old
            if previous is not None and (source.role != 'rain' or value is not None):
                amount = 0 if value is None else value - previous if value >= previous else value
                self.interval(source, t, stamp, previous, amount, zone, value)
        if not old or stamp >= old[0]:
            self.previous[key] = (stamp, value)

    def apply_live(self, samples, zone):
        for source, stamp, value in samples:
            self.feed(source, stamp, value, zone)

    def import_series(self, source, rows, start, end, zone, seed=False):
        """Replay Recorder in timestamp order without altering the live cursor."""
        key = (source.role, source.key)
        saved = self.previous.pop(key, None)
        try:
            valid = sorted([(state.last_updated.timestamp(), source.value(state)) for state in rows], key=lambda p: p[0])
            for stamp, value in valid:
                if stamp <= end:
                    self.feed(source, max(start, stamp), value, zone, live=False)
            # A missing baseline is not evidence of dry weather. A retained,
            # available state at/before start is a real baseline even if old.
            if key in self.previous and end > self.previous[key][0]:
                self.feed(source, end, self.previous[key][1], zone, live=False)
        finally:
            latest = self.previous.pop(key, None)
            if saved is not None:
                self.previous[key] = saved
            elif seed and latest is not None:
                self.previous[key] = latest

    def flush(self):
        if not self.dirty:
            return
        with sqlite3.connect(self.path) as db:
            db.executemany('INSERT OR REPLACE INTO hours VALUES (?,?,?,?,?,?,?,?,?,?)',
                           [(*key, *self.cache[key]) for key in self.dirty])
        self.dirty.clear()
        # Keep only current/recent buckets cached after historical imports.
        if len(self.cache) > 1000:
            cutoff = datetime.now(UTC).timestamp() - 172800
            self.cache = {key: row for key, row in self.cache.items() if key[2] >= cutoff}

    def imported(self, source, day):
        with sqlite3.connect(self.path) as db:
            return db.execute('SELECT 1 FROM imports WHERE source=? AND day=?', (source.key + ':' + source.role, day)).fetchone() is not None

    def mark_imported(self, source, day):
        with sqlite3.connect(self.path) as db:
            db.execute('INSERT OR IGNORE INTO imports VALUES (?,?)', (source.key + ':' + source.role, day))

    def read(self, source, start, end):
        self.flush()
        with sqlite3.connect(self.path) as db:
            rows = db.execute('SELECT t,integral,seconds,minimum,maximum,amount,end FROM hours WHERE role=? AND source=? AND t>=? AND t<? ORDER BY t', (source.role, source.key, start, end)).fetchall()
            first = db.execute('SELECT MIN(t) FROM hours WHERE role=? AND source=?', (source.role, source.key)).fetchone()[0]
        return rows, first


def period_range(day, scale, zone):
    if scale == 'month':
        first = day.replace(day=1)
        last = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
    else:
        first = day - timedelta(days=6) if scale == 'week' else day
        last = day + timedelta(days=1)
    return first, last, boundaries(first, zone)[0], boundaries(last, zone)[0]


def summarize(rows, rain, expected):
    seconds = sum(row[2] for row in rows)
    if not seconds:
        return {'value': None, 'min': None, 'max': None, 'seconds': 0, 'partial': expected > 0}
    return {'value': round(sum(row[5] for row in rows) if rain else sum(row[1] for row in rows) / seconds, 6),
            'min': min(row[5] if rain else row[3] for row in rows if row[3] is not None),
            'max': max(row[5] if rain else row[4] for row in rows if row[4] is not None),
            'seconds': round(seconds), 'partial': seconds < max(0, expected - 1)}


def recorder_day(hass, start, end, entity_ids):
    """Read detailed states and actual Recorder uptime in its database executor."""
    from sqlalchemy import select, or_
    from homeassistant.components.recorder import history
    from homeassistant.components.recorder.db_schema import RecorderRuns
    from homeassistant.components.recorder.util import session_scope
    begin = datetime.fromtimestamp(start, UTC)
    finish = datetime.fromtimestamp(end, UTC)
    data = history.get_significant_states(hass, begin, finish, entity_ids=entity_ids,
                                         significant_changes_only=False, minimal_response=False, no_attributes=False)
    with session_scope(hass=hass, read_only=True) as session:
        records = session.execute(select(RecorderRuns.start, RecorderRuns.end).where(
            RecorderRuns.start < finish, or_(RecorderRuns.end.is_(None), RecorderRuns.end > begin))).all()
    def timestamp(value):
        return value.replace(tzinfo=UTC).timestamp() if value.tzinfo is None else value.timestamp()
    windows = [(timestamp(a), min(end, timestamp(b) if b else end)) for a, b in records]
    return data, windows


class ArchiveService:
    def __init__(self, hass, runtime):
        self.hass, self.runtime = hass, runtime
        self.store = HourArchive(hass.config.path('station_meteo', 'history.sqlite3'))
        self.lock = asyncio.Lock()
        self.queue = []
        self.cancels = []
        self.task = None
        self.status = 'starting'
        self.last_flush = 0
        self.stopping = False

    async def work(self, function, *args):
        # Keep the service lock held until an executor mutation really ends,
        # including unload/shutdown while a historical import is running.
        future = self.hass.async_add_executor_job(function, *args)
        try:
            return await asyncio.shield(future)
        except asyncio.CancelledError:
            await future
            raise

    async def reconfigure(self):
        if self.stopping:
            return
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        try:
            await self.import_day(datetime.now(ZoneInfo(self.zone)).date(), current=True)
        except Exception:
            self.status = 'unavailable'
            _LOGGER.warning('Weather history import unavailable after settings change', exc_info=True)
        self.sample(datetime.now(UTC).timestamp())
        self.task = self.hass.async_create_background_task(self.backfill(), 'Station Météo history import')

    @property
    def zone(self):
        return self.hass.config.time_zone or 'UTC'

    def current_sources(self):
        return sources(self.runtime['config'])

    async def start(self):
        await self.work(self.store.initialize)
        # Seed today's history before live sampling, so no same-hour prefixes
        # can be overwritten or counted twice by the background import.
        try:
            await self.import_day(datetime.now(ZoneInfo(self.zone)).date(), current=True)
        except Exception:  # Recorder must not prevent station setup.
            self.status = 'unavailable'
            _LOGGER.warning('Initial weather history import unavailable', exc_info=True)
        self.sample(datetime.now(UTC).timestamp())
        self.cancels = [self.hass.bus.async_listen(EVENT_STATE_CHANGED, self.changed),
                        async_track_time_interval(self.hass, self.tick, timedelta(minutes=1)),
                        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.shutdown)]
        self.task = self.hass.async_create_background_task(self.backfill(), 'Station Météo history import')

    @callback
    def changed(self, event):
        if self.stopping:
            return
        state = event.data.get('new_state')
        eid = event.data.get('entity_id')
        stamp = event.time_fired.timestamp()
        for source in self.current_sources():
            if source.entity == eid:
                self.queue.append((source, stamp, source.value(state)))

    def sample(self, stamp):
        for source in self.current_sources():
            self.queue.append((source, stamp, source.value(self.hass.states.get(source.entity))))

    async def drain(self, flush=False):
        async with self.lock:
            samples, self.queue = self.queue, []
            await self.work(self.store.apply_live, samples, self.zone)
            if flush:
                await self.work(self.store.flush)

    async def tick(self, now):
        if self.stopping:
            return
        self.sample(now.timestamp())
        try:
            stamp = now.timestamp()
            await self.drain(stamp - self.last_flush >= 300)
            if stamp - self.last_flush >= 300:
                self.last_flush = stamp
        except Exception:
            _LOGGER.exception('Weather history could not be saved')

    async def shutdown(self, event):
        await self.stop()

    async def stop(self):
        if self.stopping:
            return
        self.stopping = True
        for cancel in self.cancels:
            cancel()
        self.cancels.clear()
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        self.sample(datetime.now(UTC).timestamp())
        await self.drain(True)

    async def import_day(self, day, current=False):
        if 'recorder' not in self.hass.config.components:
            self.status = 'unavailable'
            return
        from homeassistant.components.recorder import get_instance
        definitions = self.current_sources()
        if not current:
            async with self.lock:
                definitions = [source for source in definitions if not await self.work(self.store.imported, source, day.isoformat())]
        if not definitions:
            return
        start, end = boundaries(day, self.zone)
        end = min(end, datetime.now(UTC).timestamp())
        if end <= start:
            return
        recorder = get_instance(self.hass)
        query = partial(recorder_day, self.hass, start, end, list({source.entity for source in definitions}))
        data, windows = await recorder.async_add_executor_job(query)
        async with self.lock:
            for source in definitions:
                for run_start, run_end in sorted(windows):
                    begin, finish = max(start, run_start), min(end, run_end)
                    if finish <= begin:
                        continue
                    # Never carry a pre-shutdown state through a Recorder outage.
                    states = [state for state in data.get(source.entity, []) if run_start <= state.last_updated.timestamp() <= finish]
                    await self.work(self.store.import_series, source, states, begin, finish, self.zone, current and finish == end)
            await self.work(self.store.flush)
            if not current:
                for source in definitions:
                    await self.work(self.store.mark_imported, source, day.isoformat())

    async def backfill(self):
        self.status = 'importing'
        try:
            if 'recorder' not in self.hass.config.components:
                self.status = 'unavailable'
                return
            # Retained detailed Recorder states (not long-term hourly means).
            # Sixty days cover the user's configured retention. Older days can
            # still be requested explicitly in the date selector.
            today = datetime.now(ZoneInfo(self.zone)).date()
            for offset in range(1, 61):
                await self.import_day(today - timedelta(days=offset))
                await asyncio.sleep(0)
            self.status = 'ready'
        except asyncio.CancelledError:
            raise
        except Exception:
            self.status = 'unavailable'
            _LOGGER.warning('Weather history import paused; local collection continues', exc_info=True)

    async def query(self, role, day, scale):
        source = next((s for s in self.current_sources() if s.role == role), None)
        first, last, start, end = period_range(day, scale, self.zone)
        today = datetime.now(ZoneInfo(self.zone)).date()
        if first > today or first.year < 2000:
            raise ValueError('Invalid history period')
        # Import older detailed days on demand if outside the initial window.
        if source and first < today - timedelta(days=60) and 'recorder' in self.hass.config.components:
            cursor = first
            while cursor < last and cursor <= today:
                try:
                    await self.import_day(cursor)
                except Exception:
                    self.status = 'unavailable'
                    break
                cursor += timedelta(days=1)
        self.sample(datetime.now(UTC).timestamp())
        await self.drain()
        async with self.lock:
            rows, earliest = await self.work(self.store.read, source, start, end) if source else ([], None)
            gust_source = next((s for s in self.current_sources() if s.role == 'wind_gust'), None)
            gust_rows = (await self.work(self.store.read, gust_source, start, end))[0] if role == 'wind_speed' and gust_source else []
        now = datetime.now(UTC).timestamp()
        points = []
        cursor = start
        while cursor < end:
            stop = min(cursor + 3600, end) if scale == 'hour' else boundaries(datetime.fromtimestamp(cursor, ZoneInfo(self.zone)).date() + timedelta(days=1), self.zone)[0]
            group = [row for row in rows if cursor <= row[0] < stop]
            expected = max(0, min(stop, now) - cursor)
            item = {'t': cursor * 1000, 'end': stop * 1000, 'ongoing': cursor <= now < stop, **summarize(group, role == 'rain', expected)}
            if role == 'wind_speed':
                gusts = [row[4] for row in gust_rows if cursor <= row[0] < stop and row[4] is not None]
                item['gust'] = max(gusts) if gusts else None
            points.append(item)
            cursor = stop
        return {'role': role, 'scale': scale, 'date': day.isoformat(), 'start': first.isoformat(), 'end': (last - timedelta(days=1)).isoformat(),
                'points': points, 'summary': summarize(rows, role == 'rain', max(0, min(end, now) - start)),
                'earliest': datetime.fromtimestamp(earliest, ZoneInfo(self.zone)).date().isoformat() if earliest is not None else None,
                'today': today.isoformat(), 'import_status': self.status, 'estimated': bool(source and source.kind == 'lux'), 'configured': source is not None}
