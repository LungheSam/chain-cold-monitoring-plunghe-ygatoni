"""Shared helpers for the unit tests."""
from coldchain.alarm import AlarmEngine, Reading
from coldchain.clock import FakeClock
from coldchain.config import load_settings


def make_engine(profile="demo", synced=True):
    clock = FakeClock(synced=synced)
    engine = AlarmEngine(load_settings({"PROFILE": profile}), clock)
    return engine, clock


def reading(temp=5.0, amb=24.0, hum=60.0, door=False, mains=True):
    return Reading(internal_temp=temp, ambient_temp=amb, humidity=hum, door_open=door, mains_present=mains)


def run(engine, clock, seconds, step=1.0, **kwargs):
    """Feed the same reading every `step` seconds for `seconds`. Returns all events."""
    events = []
    t = 0.0
    while t < seconds - 1e-9:
        clock.advance(step)
        t += step
        events += engine.update(reading(**kwargs))
    return events


def types(events):
    return [e["type"] for e in events]
