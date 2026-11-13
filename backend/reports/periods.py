"""
Report periods.

One report timezone (Asia/Manila, a fixed UTC+08:00 offset — the Philippines
has no daylight saving). Storage is UTC. Every period is start-inclusive and
end-exclusive; custom ranges include the whole of their end date.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone


REPORT_TZ = timezone(timedelta(hours=8))
REPORT_TZ_LABEL = "Asia/Manila (UTC+08:00)"

MAX_CUSTOM_DAYS = 366


@dataclass(frozen=True)
class Period:
    kind: str            # "weekly" | "monthly" | "custom"
    start: date          # first local day (inclusive)
    end: date            # local day after the last day (exclusive)
    label: str

    @property
    def start_utc(self):
        return datetime.combine(self.start, time.min, tzinfo=REPORT_TZ).astimezone(timezone.utc)

    @property
    def end_utc(self):
        return datetime.combine(self.end, time.min, tzinfo=REPORT_TZ).astimezone(timezone.utc)

    @property
    def last_day(self):
        return self.end - timedelta(days=1)

    @property
    def days(self):
        return (self.end - self.start).days

    def contains(self, moment):
        return moment is not None and self.start_utc <= moment < self.end_utc


def _fmt(day):
    return f"{day:%b} {day.day}, {day.year}"


def weekly_period(any_day):
    """The ISO week (Monday to Sunday) containing any_day."""

    monday = any_day - timedelta(days=any_day.weekday())
    iso_year, iso_week, _ = monday.isocalendar()
    end = monday + timedelta(days=7)

    return Period(
        "weekly",
        monday,
        end,
        f"ISO week {iso_year}-W{iso_week:02d} ({_fmt(monday)} – {_fmt(end - timedelta(days=1))})",
    )


def monthly_period(year, month):
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)

    return Period("monthly", start, end, f"{start:%B %Y}")


def custom_period(first_day, last_day):
    """Inclusive local dates first_day..last_day."""

    if last_day < first_day:
        raise ValueError("The end date must be on or after the start date.")

    end = last_day + timedelta(days=1)

    if (end - first_day).days > MAX_CUSTOM_DAYS:
        raise ValueError(f"Custom periods are limited to {MAX_CUSTOM_DAYS} days.")

    return Period("custom", first_day, end, f"{_fmt(first_day)} – {_fmt(last_day)}")


def to_local_date(moment):
    return moment.astimezone(REPORT_TZ).date()


def parse_timestamp(value):
    """ISO string or datetime -> aware UTC datetime; None when missing/invalid."""

    if value is None or value == "":
        return None

    if isinstance(value, datetime):
        moment = value
    else:
        try:
            moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None

    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)

    return moment.astimezone(timezone.utc)
