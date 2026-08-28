from datetime import datetime, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

from django.utils import timezone

from .exceptions import SLAError


class BusinessTimeCalculator:
    MAX_DAYS=3660
    @staticmethod
    def _snapshot(calendar):
        if hasattr(calendar,"schedule_snapshot"):return calendar.timezone,calendar.schedule_snapshot,calendar.exceptions_snapshot
        if not calendar.current_version_id:raise SLAError("Calendar has no published version.",code="sla_calendar_invalid")
        version=calendar.current_version;return version.timezone,version.schedule_snapshot,version.exceptions_snapshot
    @classmethod
    def _intervals(cls,calendar,date):
        tz_name,schedule,exceptions=cls._snapshot(calendar);zone=ZoneInfo(tz_name);exception=exceptions.get(date.isoformat())
        if exception:
            if exception["type"]=="non_working_day":return []
            raw=exception.get("intervals") or schedule.get(str(date.weekday()),[])
        else:raw=schedule.get(str(date.weekday()),[])
        result=[]
        for item in raw:
            start=datetime.combine(date,datetime.strptime(item["start"],"%H:%M:%S").time(),zone);end=datetime.combine(date,datetime.strptime(item["end"],"%H:%M:%S").time(),zone);result.append((start,end))
        return result
    @classmethod
    def is_working_time(cls,calendar,dt):
        if not timezone.is_aware(dt):raise SLAError("Datetime must be timezone-aware.",code="sla_calendar_invalid")
        zone=ZoneInfo(cls._snapshot(calendar)[0]);local=dt.astimezone(zone);return any(start<=local<end for start,end in cls._intervals(calendar,local.date()))
    @classmethod
    def next_working_time(cls,calendar,dt):
        if not timezone.is_aware(dt):raise SLAError("Datetime must be timezone-aware.",code="sla_calendar_invalid")
        zone=ZoneInfo(cls._snapshot(calendar)[0]);cursor=dt.astimezone(zone)
        for offset in range(cls.MAX_DAYS):
            date=(cursor+timedelta(days=offset)).date()
            for start,end in cls._intervals(calendar,date):
                if offset==0 and start<=cursor<end:return cursor
                if start>=cursor:return start
        raise SLAError("Calendar has no future working time.",code="sla_calendar_invalid")
    @classmethod
    def add_business_duration(cls,calendar,start_at,duration):
        seconds=duration.total_seconds() if hasattr(duration,"total_seconds") else float(duration)
        if seconds<0:raise SLAError("Duration cannot be negative.",code="sla_calendar_invalid")
        cursor=cls.next_working_time(calendar,start_at);remaining=seconds
        while remaining>0:
            interval=next((pair for pair in cls._intervals(calendar,cursor.date()) if pair[0]<=cursor<pair[1]),None)
            if interval is None:cursor=cls.next_working_time(calendar,cursor+timedelta(microseconds=1));continue
            available=(interval[1].astimezone(dt_timezone.utc)-cursor.astimezone(dt_timezone.utc)).total_seconds()
            if remaining<=available:return (cursor.astimezone(dt_timezone.utc)+timedelta(seconds=remaining)).astimezone(ZoneInfo(cls._snapshot(calendar)[0]))
            remaining-=available;cursor=cls.next_working_time(calendar,interval[1]+timedelta(microseconds=1))
        return cursor
    @classmethod
    def business_duration_between(cls,calendar,start_at,end_at):
        if end_at<start_at:return -cls.business_duration_between(calendar,end_at,start_at)
        zone=ZoneInfo(cls._snapshot(calendar)[0]);start=start_at.astimezone(zone);end=end_at.astimezone(zone);total=0.0;date=start.date()
        while date<=end.date():
            for left,right in cls._intervals(calendar,date):
                lo=max(left,start);hi=min(right,end)
                if hi>lo:total+=(hi.astimezone(dt_timezone.utc)-lo.astimezone(dt_timezone.utc)).total_seconds()
            date+=timedelta(days=1)
        return timedelta(seconds=total)
