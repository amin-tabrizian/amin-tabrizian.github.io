#!/usr/bin/env python3
"""Merge calendar feeds into busy blocks for calendar/busy.json.

Reads iCal feed URLs from the environment variables in FEEDS, keeps only the
start and end of busy events, and writes them per day in Eastern Time.
Titles, locations, and attendees are never written or printed.

Usage: python scripts/build_busy.py calendar/busy.json
"""
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import icalendar
import recurring_ical_events

TZ = ZoneInfo("America/New_York")
WEEKS = 5
FEEDS = ("GWU_ICS_URL", "CIGNUS_ICS_URL")


def normalize(url):
    url = url.strip().strip("\"'<>`").strip()
    if url.startswith("webcal://"):
        url = "https://" + url[len("webcal://"):]
    # Outlook publishes an HTML link and an ICS link; only the ICS one is a feed.
    if "outlook." in url and url.endswith("/calendar.html"):
        url = url[: -len("html")] + "ics"
    # A Google Calendar share link (?cid=...) names the calendar; use its public iCal feed.
    cid = re.search(r"[?&]cid=([^&#]+)", url)
    if cid and "calendar.google.com" in url:
        raw = urllib.parse.unquote(cid.group(1))
        cal_id = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)).decode()
        url = "https://calendar.google.com/calendar/ical/" + urllib.parse.quote(cal_id) + "/public/basic.ics"
    return url


def fetch(url):
    req = urllib.request.Request(normalize(url), headers={"User-Agent": "busy-times/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read()
    if not body.lstrip(b"\xef\xbb\xbf \r\n\t").startswith(b"BEGIN:VCALENDAR"):
        raise NotICal("response is not an iCal feed; use the .ics link")
    return body


class NotICal(Exception):
    pass


def fail(message):
    # On GitHub Actions, also show the message as an annotation on the run page.
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::error::{message}")
    sys.exit(message)


def to_local(value):
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=TZ)
        return value.astimezone(TZ)
    return datetime.combine(value, time.min, tzinfo=TZ)


def is_busy(event):
    if str(event.get("STATUS", "")).upper() == "CANCELLED":
        return False
    if str(event.get("TRANSP", "OPAQUE")).upper() == "TRANSPARENT":
        return False
    if str(event.get("X-MICROSOFT-CDO-BUSYSTATUS", "")).upper() == "FREE":
        return False
    return True


def busy_intervals(ics, start, end):
    cal = icalendar.Calendar.from_ical(ics)
    for event in recurring_ical_events.of(cal).between(start, end):
        if not is_busy(event):
            continue
        begin = event["DTSTART"].dt
        if "DTEND" in event:
            finish = event["DTEND"].dt
        elif "DURATION" in event:
            finish = begin + event["DURATION"].dt
        else:
            finish = begin + timedelta(days=1) if not isinstance(begin, datetime) else begin
        yield to_local(begin), to_local(finish)


def split_by_day(intervals, start, end):
    days = {}
    for s, e in intervals:
        s, e = max(s, start), min(e, end)
        while s < e:
            next_midnight = datetime.combine(s.date() + timedelta(days=1), time.min, tzinfo=TZ)
            seg_end = min(e, next_midnight)
            a = s.hour * 60 + s.minute
            b = 1440 if seg_end == next_midnight else seg_end.hour * 60 + seg_end.minute
            if b > a:
                days.setdefault(s.date().isoformat(), []).append([a, b])
            s = seg_end
    return days


def merge(blocks):
    merged = []
    for a, b in sorted(blocks):
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return merged


def main(out_path):
    today = datetime.now(TZ).date()
    monday = today - timedelta(days=today.weekday())
    start = datetime.combine(monday, time.min, tzinfo=TZ)
    end = datetime.combine(monday + timedelta(weeks=WEEKS), time.min, tzinfo=TZ)

    configured = [name for name in FEEDS if os.environ.get(name, "").strip()]
    print("Feeds configured:", ", ".join(configured) or "none")
    if not configured:
        fail("No calendar feeds configured. Set " + " and ".join(FEEDS) + ".")

    intervals = []
    for name in configured:
        try:
            found = list(busy_intervals(fetch(os.environ[name]), start, end))
        # Exit without writing, so the site keeps the last good data instead of partial data.
        # Messages never include the feed URL, since some feed URLs are private.
        except urllib.error.HTTPError as exc:
            fail(f"{name}: could not read feed (HTTP {exc.code}).")
        except NotICal as exc:
            fail(f"{name}: {exc}.")
        except Exception as exc:
            fail(f"{name}: could not read feed ({type(exc).__name__}).")
        print(f"{name}: {len(found)} busy events")
        intervals.extend(found)

    days = {d: merge(blocks) for d, blocks in sorted(split_by_day(intervals, start, end).items())}
    data = {"tz": "America/New_York", "start": monday.isoformat(), "weeks": WEEKS, "days": days}

    try:
        with open(out_path) as f:
            if json.load(f) == data:
                print("No change")
                return
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(data, f, separators=(",", ":"))
        f.write("\n")
    print(f"Wrote {sum(len(b) for b in days.values())} busy blocks over {len(days)} days")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "calendar/busy.json")
