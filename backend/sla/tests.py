from datetime import date, datetime, time, timedelta, timezone as dt_timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from audit.models import AuditEvent
from employees.models import Employee
from events.models import OutboxEvent
from organizations.models import LegalEntity, Location, OrgUnit
from service_requests.models import RequestType, Service, ServiceCategory

from .calendars import BusinessTimeCalculator
from .exceptions import SLAError, SLAPolicyAmbiguous
from .models import (BusinessCalendar, BusinessCalendarException,
                     BusinessCalendarWorkingInterval, CalendarExceptionType,
                     MetricType, PausePolicy, SLAPolicy,
                     SLAPolicyAssignmentRule, TimeMode)
from .services import CalendarService, SLAPolicyResolver, SLAPolicyService


class SLATestCase(TestCase):
    def setUp(self):
        self.user=User.objects.create_superuser(username="sla-admin",email="sla@test.local",password="x");self.actor=Employee.objects.create(user=self.user,first_name="SLA")
        self.le=LegalEntity.objects.create(name="SLA LE");self.unit=OrgUnit.objects.create(name="SLA Unit",legal_entity=self.le);self.location=Location.objects.create(name="SLA Location",legal_entity=self.le)
    def calendar(self,timezone="Asia/Novosibirsk",publish=True):
        calendar=BusinessCalendar.objects.create(name="Office",code=f"CAL_{BusinessCalendar.objects.count()}",timezone=timezone,created_by=self.actor)
        for weekday in range(5):CalendarService.save_interval(calendar=calendar,actor=self.actor,user=self.user,weekday=weekday,start_time=time(9),end_time=time(18),position=1,is_active=True)
        if publish:CalendarService.publish(calendar=calendar,actor=self.actor,user=self.user)
        return calendar
    def policy(self,calendar=None,mode=TimeMode.ELAPSED_TIME,code=None):
        return SLAPolicy.objects.create(name="Policy",code=code or f"POL_{SLAPolicy.objects.count()}",draft_time_mode=mode,draft_calendar=calendar,draft_response_duration_seconds=1800,draft_resolution_duration_seconds=14400,draft_pause_policy=PausePolicy.BOTH,draft_thresholds=[{"metric_type":"response","threshold_percent":50},{"metric_type":"response","threshold_percent":100},{"metric_type":"resolution","threshold_percent":80}],created_by=self.actor)


class CalendarValidationAndVersionTests(SLATestCase):
    def test_timezone_overlap_and_invalid_interval(self):
        calendar=BusinessCalendar.objects.create(name="Invalid",code="INVALID",timezone="Bad/Zone",created_by=self.actor)
        with self.assertRaises(SLAError):CalendarService.publish(calendar=calendar,actor=self.actor,user=self.user)
        calendar.timezone="Asia/Novosibirsk";calendar.save(update_fields=["timezone"])
        CalendarService.save_interval(calendar=calendar,actor=self.actor,user=self.user,weekday=0,start_time=time(9),end_time=time(13))
        with self.assertRaises(SLAError):CalendarService.save_interval(calendar=calendar,actor=self.actor,user=self.user,weekday=0,start_time=time(12),end_time=time(15))
        with self.assertRaises(SLAError):CalendarService.save_interval(calendar=calendar,actor=self.actor,user=self.user,weekday=1,start_time=time(15),end_time=time(10))
    def test_calendar_versions_are_immutable_snapshots_and_atomic(self):
        calendar=self.calendar(publish=False);v1=CalendarService.publish(calendar=calendar,actor=self.actor,user=self.user);interval=calendar.working_intervals.get(weekday=0);interval.end_time=time(17);interval.save(update_fields=["end_time"]);v2=CalendarService.publish(calendar=calendar,actor=self.actor,user=self.user)
        self.assertEqual(v1.schedule_snapshot["0"][0]["end"],"18:00:00");self.assertEqual(v2.schedule_snapshot["0"][0]["end"],"17:00:00")
        v1.timezone="UTC"
        with self.assertRaises(ValidationError):v1.save()
        before=calendar.versions.count()
        with patch("sla.services.DomainEventService.publish",side_effect=RuntimeError("outbox")):
            with self.assertRaises(RuntimeError):CalendarService.publish(calendar=calendar,actor=self.actor,user=self.user)
        self.assertEqual(calendar.versions.count(),before)


class BusinessTimeCalculatorTests(SLATestCase):
    def test_friday_to_monday_outside_hours_and_between(self):
        calendar=self.calendar();zone=ZoneInfo(calendar.timezone)
        friday=datetime(2026,8,28,17,tzinfo=zone);due=BusinessTimeCalculator.add_business_duration(calendar,friday,7200);self.assertEqual(due,datetime(2026,8,31,10,tzinfo=zone));self.assertEqual(BusinessTimeCalculator.business_duration_between(calendar,friday,due),timedelta(hours=2))
        monday=datetime(2026,8,31,7,tzinfo=zone);self.assertEqual(BusinessTimeCalculator.add_business_duration(calendar,monday,3600),datetime(2026,8,31,10,tzinfo=zone));self.assertEqual(BusinessTimeCalculator.next_working_time(calendar,datetime(2026,8,31,20,tzinfo=zone)),datetime(2026,9,1,9,tzinfo=zone))
    def test_holiday_custom_hours_and_lunch(self):
        calendar=self.calendar(publish=False);holiday=BusinessCalendarException.objects.create(calendar=calendar,date=date(2026,8,31),exception_type=CalendarExceptionType.NON_WORKING_DAY,created_by=self.actor)
        CalendarService.publish(calendar=calendar,actor=self.actor,user=self.user);zone=ZoneInfo(calendar.timezone);self.assertEqual(BusinessTimeCalculator.add_business_duration(calendar,datetime(2026,8,28,17,tzinfo=zone),7200),datetime(2026,9,1,10,tzinfo=zone))
        holiday.delete();CalendarService.save_exception(calendar=calendar,actor=self.actor,user=self.user,date=date(2026,8,31),exception_type=CalendarExceptionType.CUSTOM_HOURS,intervals=[{"start_time":time(10),"end_time":time(14)}]);CalendarService.publish(calendar=calendar,actor=self.actor,user=self.user);self.assertEqual(BusinessTimeCalculator.next_working_time(calendar,datetime(2026,8,31,9,tzinfo=zone)),datetime(2026,8,31,10,tzinfo=zone))
        lunch=BusinessCalendar.objects.create(name="Lunch",code="LUNCH",timezone="UTC",created_by=self.actor);CalendarService.save_interval(calendar=lunch,actor=self.actor,user=self.user,weekday=0,start_time=time(9),end_time=time(13));CalendarService.save_interval(calendar=lunch,actor=self.actor,user=self.user,weekday=0,start_time=time(14),end_time=time(18));CalendarService.publish(calendar=lunch,actor=self.actor,user=self.user);self.assertEqual(BusinessTimeCalculator.business_duration_between(lunch,datetime(2026,8,31,12,tzinfo=dt_timezone.utc),datetime(2026,8,31,15,tzinfo=dt_timezone.utc)),timedelta(hours=2))
    def test_24x7_timezone_and_dst(self):
        calendar=BusinessCalendar.objects.create(name="24x7",code="ALL",timezone="UTC",created_by=self.actor)
        for weekday in range(7):CalendarService.save_interval(calendar=calendar,actor=self.actor,user=self.user,weekday=weekday,start_time=time(0),end_time=time(23,59,59,999999))
        CalendarService.publish(calendar=calendar,actor=self.actor,user=self.user);start=datetime(2026,8,31,10,tzinfo=dt_timezone.utc);self.assertEqual(BusinessTimeCalculator.add_business_duration(calendar,start,3600),start+timedelta(hours=1))
        dst=BusinessCalendar.objects.create(name="DST",code="DST",timezone="Europe/Berlin",created_by=self.actor);CalendarService.save_interval(calendar=dst,actor=self.actor,user=self.user,weekday=6,start_time=time(0),end_time=time(23));CalendarService.publish(calendar=dst,actor=self.actor,user=self.user);zone=ZoneInfo("Europe/Berlin");self.assertEqual(BusinessTimeCalculator.business_duration_between(dst,datetime(2026,3,29,0,tzinfo=zone),datetime(2026,3,29,4,tzinfo=zone)),timedelta(hours=3))


class PolicyVersionAndResolverTests(SLATestCase):
    def setUp(self):
        super().setUp();self.category=ServiceCategory.objects.create(name="IT");self.service=Service.objects.create(category=self.category,name="Support");self.rt=RequestType.objects.create(service=self.service,name="Incident",code="SLA_INCIDENT",created_by=self.actor)
    def test_policy_validation_thresholds_versions_and_atomicity(self):
        invalid=self.policy(mode=TimeMode.BUSINESS_TIME)
        with self.assertRaises(SLAError):SLAPolicyService.publish(policy=invalid,actor=self.actor,user=self.user)
        calendar=self.calendar();policy=self.policy(calendar=calendar,mode=TimeMode.BUSINESS_TIME);v1=SLAPolicyService.publish(policy=policy,actor=self.actor,user=self.user);self.assertEqual(v1.warning_thresholds.count(),3);policy.draft_response_duration_seconds=900;policy.save(update_fields=["draft_response_duration_seconds"]);v2=SLAPolicyService.publish(policy=policy,actor=self.actor,user=self.user);self.assertEqual(v1.response_duration_seconds,1800);self.assertEqual(v2.response_duration_seconds,900)
        v1.response_duration_seconds=1
        with self.assertRaises(ValidationError):v1.save()
        policy.draft_thresholds=[{"metric_type":"response","threshold_percent":0}];policy.save(update_fields=["draft_thresholds"])
        with self.assertRaises(SLAError):SLAPolicyService.publish(policy=policy,actor=self.actor,user=self.user)
        policy.draft_thresholds=[{"metric_type":"response","threshold_percent":50}];policy.save(update_fields=["draft_thresholds"]);before=policy.versions.count()
        with patch("sla.services.AuditService.record",side_effect=RuntimeError("audit")):
            with self.assertRaises(RuntimeError):SLAPolicyService.publish(policy=policy,actor=self.actor,user=self.user)
        self.assertEqual(policy.versions.count(),before)
    def test_resolver_specificity_ambiguity_effective_and_none(self):
        fallback=self.policy(code="FALLBACK");specific=self.policy(code="SPECIFIC");fallback_v=SLAPolicyService.publish(policy=fallback,actor=self.actor,user=self.user);specific_v=SLAPolicyService.publish(policy=specific,actor=self.actor,user=self.user)
        fallback_rule=SLAPolicyAssignmentRule.objects.create(policy=fallback,order=10);SLAPolicyAssignmentRule.objects.create(policy=specific,request_type=self.rt,request_priority="critical",location=self.location,order=100)
        self.assertEqual(SLAPolicyResolver.resolve(request_type=self.rt,priority="critical",location=self.location),specific_v);self.assertEqual(SLAPolicyResolver.resolve(request_type=self.rt,priority="normal"),fallback_v)
        SLAPolicyAssignmentRule.objects.create(policy=self.policy(code="UNPUBLISHED"),service=self.service)
        fallback_rule.is_active=False;fallback_rule.save(update_fields=["is_active"])
        self.assertIsNone(SLAPolicyResolver.resolve(request_type=None,service=None,priority="low",legal_entity=self.le))
        fallback_rule.is_active=True;fallback_rule.save(update_fields=["is_active"])
        duplicate=self.policy(code="DUP");SLAPolicyService.publish(policy=duplicate,actor=self.actor,user=self.user);SLAPolicyAssignmentRule.objects.create(policy=duplicate,order=10)
        with self.assertRaises(SLAPolicyAmbiguous):SLAPolicyResolver.resolve(request_type=self.rt,priority="normal")
    def test_preview_api_business_and_elapsed(self):
        calendar=self.calendar();policy=self.policy(calendar=calendar,mode=TimeMode.BUSINESS_TIME);SLAPolicyService.publish(policy=policy,actor=self.actor,user=self.user);SLAPolicyAssignmentRule.objects.create(policy=policy,request_type=self.rt)
        client=APIClient();client.force_authenticate(self.user);response=client.post("/api/internal/v1/sla/policy-preview/",{"request_type":str(self.rt.pk),"priority":"normal"},format="json");self.assertEqual(response.status_code,200,response.data);self.assertEqual(response.data["policy_version"],1)
        start="2026-08-28T17:00:00+07:00";response=client.post("/api/internal/v1/sla/deadline-preview/",{"calendar":str(calendar.pk),"time_mode":"business_time","start_at":start,"duration_seconds":7200},format="json");self.assertEqual(response.status_code,200,response.data)
        response=client.post("/api/internal/v1/sla/deadline-preview/",{"time_mode":"elapsed_time","start_at":start,"duration_seconds":3600},format="json");self.assertEqual(response.status_code,200,response.data)
