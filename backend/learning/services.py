import random
import uuid
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.core.files.base import ContentFile
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from audit.services import record
from .models import (AssessmentAttempt, AssessmentResponse, Certificate,
                     CourseAssignment, LessonProgress, Question)


def _certificate_pdf(certificate):
    lines = [
        "BT /F1 22 Tf 72 740 Td (AYS Connect Certificate) Tj ET",
        f"BT /F1 12 Tf 72 700 Td (Number: {certificate.certificate_number}) Tj ET",
        f"BT /F1 12 Tf 72 675 Td (Verification: {certificate.verification_code}) Tj ET",
        f"BT /F1 12 Tf 72 650 Td (Employee ID: {certificate.employee_id}) Tj ET",
        f"BT /F1 12 Tf 72 625 Td (Course ID: {certificate.course_id}) Tj ET",
    ]
    stream = "\n".join(lines).encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(pdf)); pdf.extend(f"{index} 0 obj\n".encode()); pdf.extend(obj); pdf.extend(b"\nendobj\n")
    xref = len(pdf); pdf.extend(f"xref\n0 {len(objects)+1}\n".encode()); pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]: pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(pdf)


@transaction.atomic
def start_assignment(*, assignment, actor, request=None):
    if assignment.employee.user_id != actor.id:
        raise ValidationError("Запустить можно только собственное обучение")
    if assignment.status not in {CourseAssignment.Status.ASSIGNED, CourseAssignment.Status.NOT_STARTED}:
        raise ValidationError("Обучение нельзя запустить из текущего статуса")
    first_lesson = assignment.course.modules.order_by("sort_order", "id").values_list("lessons__id", flat=True).exclude(lessons__id=None).first()
    assignment.status = CourseAssignment.Status.IN_PROGRESS
    assignment.started_at = assignment.started_at or timezone.now()
    assignment.current_lesson_id = first_lesson
    assignment.save(update_fields=["status", "started_at", "current_lesson"])
    record(actor, "learning.assignment_started", assignment, request=request)
    return assignment


@transaction.atomic
def complete_lesson(*, assignment, lesson, actor, confirmed=False, time_spent_seconds=0, request=None):
    if assignment.employee.user_id != actor.id:
        raise ValidationError("Завершить можно только собственный урок")
    if lesson.module.course_id != assignment.course_id:
        raise ValidationError("Урок не относится к назначенному курсу")
    if assignment.status not in {CourseAssignment.Status.IN_PROGRESS, CourseAssignment.Status.ASSIGNED, CourseAssignment.Status.NOT_STARTED}:
        raise ValidationError("Урок нельзя завершить в текущем статусе назначения")
    if lesson.requires_confirmation and not confirmed:
        raise ValidationError("Необходимо подтвердить изучение урока")
    now = timezone.now()
    progress, _ = LessonProgress.objects.get_or_create(assignment=assignment, lesson=lesson)
    progress.opened_at = progress.opened_at or now
    progress.completed_at = now
    progress.progress_percent = 100
    progress.confirmed = bool(confirmed or not lesson.requires_confirmation)
    progress.confirmed_at = now if progress.confirmed else None
    progress.time_spent_seconds += max(0, int(time_spent_seconds or 0))
    progress.save()
    required_ids = list(assignment.course.modules.filter(is_required=True, lessons__is_required=True).values_list("lessons__id", flat=True).exclude(lessons__id=None))
    completed_ids = set(assignment.lesson_progress.filter(completed_at__isnull=False).values_list("lesson_id", flat=True))
    total = len(required_ids)
    completed = sum(1 for lesson_id in required_ids if lesson_id in completed_ids)
    assignment.progress_percent = 100 if total == 0 else round(completed * 100 / total)
    remaining = assignment.course.modules.values_list("lessons__id", flat=True).exclude(lessons__id=None).exclude(lessons__id__in=completed_ids).first()
    assignment.current_lesson_id = remaining
    if assignment.progress_percent == 100:
        if assignment.course.assessments.filter(is_active=True).exists():
            assignment.status = CourseAssignment.Status.WAITING_ASSESSMENT
            assignment.completed_at = None
        else:
            assignment.status = CourseAssignment.Status.COMPLETED
            assignment.completed_at = now
    else:
        assignment.status = CourseAssignment.Status.IN_PROGRESS
        assignment.started_at = assignment.started_at or now
    assignment.save(update_fields=["progress_percent", "current_lesson", "status", "started_at", "completed_at"])
    record(actor, "learning.lesson_completed", progress, new_values={"progress_percent": assignment.progress_percent}, request=request)
    if assignment.status == CourseAssignment.Status.COMPLETED:
        from .integrations import complete_linked_task, notify_course_completed
        complete_linked_task(assignment, actor=actor)
        notify_course_completed(assignment)
        record(actor, "learning.course_completed", assignment, request=request)
    return progress, assignment


@transaction.atomic
def start_attempt(*, assessment, assignment, actor, request=None):
    if assignment.employee.user_id != actor.id or assignment.course_id != assessment.course_id:
        raise ValidationError("Тест недоступен для этого назначения")
    if not assessment.is_active:
        raise ValidationError("Тест отключён")
    active = assessment.attempts.filter(employee=assignment.employee, status=AssessmentAttempt.Status.IN_PROGRESS).first()
    if active:
        return active
    attempts_count = assessment.attempts.filter(employee=assignment.employee).exclude(status=AssessmentAttempt.Status.EXPIRED).count()
    max_attempts = min(assessment.max_attempts, assignment.course.max_attempts)
    if attempts_count >= max_attempts:
        raise ValidationError("Количество попыток исчерпано")
    questions = list(assessment.questions.prefetch_related("options").all())
    if not questions:
        raise ValidationError("В тесте нет вопросов")
    limit = assessment.questions_per_attempt or len(questions)
    if assessment.shuffle_questions:
        questions = random.sample(questions, min(limit, len(questions)))
    else:
        questions = questions[:limit]
    attempt = AssessmentAttempt.objects.create(assessment=assessment, assignment=assignment, employee=assignment.employee, attempt_number=attempts_count + 1, max_score=sum((q.points for q in questions), Decimal("0")))
    attempt.questions.set(questions)
    assignment.status = CourseAssignment.Status.WAITING_ASSESSMENT
    assignment.save(update_fields=["status"])
    record(actor, "learning.assessment_started", attempt, request=request)
    return attempt


def _auto_grade(response):
    question = response.question
    if question.manual_review_required or question.question_type in {Question.Type.TEXT, Question.Type.CASE_STUDY}:
        response.is_correct = None
        return False
    if question.question_type == Question.Type.NUMBER:
        correct = question.options.filter(is_correct=True).first()
        try:
            expected = Decimal((correct.match_key or correct.text).replace(",", ".")) if correct else None
            response.is_correct = expected is not None and response.number_answer == expected
        except (InvalidOperation, AttributeError):
            response.is_correct = False
    else:
        selected = set(response.selected_options.values_list("id", flat=True))
        correct = set(question.options.filter(is_correct=True).values_list("id", flat=True))
        response.is_correct = bool(correct) and selected == correct
    response.points_awarded = question.points if response.is_correct else Decimal("0")
    response.save(update_fields=["is_correct", "points_awarded"])
    return True


def _finalize_attempt(attempt, actor=None, request=None):
    attempt.score = sum((r.points_awarded for r in attempt.responses.all()), Decimal("0"))
    attempt.score_percent = (attempt.score * 100 / attempt.max_score).quantize(Decimal("0.01")) if attempt.max_score else Decimal("0")
    attempt.passed = attempt.score_percent >= attempt.assessment.passing_score
    attempt.status = AssessmentAttempt.Status.PASSED if attempt.passed else AssessmentAttempt.Status.FAILED
    attempt.save(update_fields=["score", "score_percent", "passed", "status"])
    assignment = attempt.assignment
    if attempt.passed:
        assignment.status = CourseAssignment.Status.COMPLETED
        assignment.progress_percent = 100
        assignment.completed_at = timezone.now()
        assignment.save(update_fields=["status", "progress_percent", "completed_at"])
        if assignment.course.certificate_enabled:
            validity = assignment.course.certificate_validity_days
            certificate, created = Certificate.objects.get_or_create(assignment=assignment, defaults={"employee": assignment.employee, "course": assignment.course, "certificate_number": f"AYS-{timezone.now():%Y%m}-{assignment.id:06d}", "verification_code": uuid.uuid4().hex, "expires_at": timezone.now() + timedelta(days=validity) if validity else None, "issued_by": actor})
            if created:
                certificate.file.save(f"{certificate.certificate_number}.pdf", ContentFile(_certificate_pdf(certificate)), save=True)
                from notifications.models import Notification
                from .integrations import notify_once
                notify_once(recipient=assignment.employee.user, notification_type=Notification.Type.CERTIFICATE_ISSUED, title="Сертификат выдан", message=f"Выдан сертификат по курсу «{assignment.course.title}».", entity_type="Certificate", entity_id=certificate.id)
                record(actor, "learning.certificate_issued", certificate, request=request)
        from .integrations import complete_linked_task, notify_course_completed
        complete_linked_task(assignment, actor=actor)
        notify_course_completed(assignment)
    else:
        used = attempt.assessment.attempts.filter(employee=attempt.employee).exclude(status=AssessmentAttempt.Status.EXPIRED).count()
        maximum = min(attempt.assessment.max_attempts, assignment.course.max_attempts)
        assignment.status = CourseAssignment.Status.FAILED if used >= maximum else CourseAssignment.Status.WAITING_ASSESSMENT
        assignment.save(update_fields=["status"])
        from notifications.models import Notification
        from .integrations import notify_once
        notify_once(recipient=assignment.employee.user, notification_type=Notification.Type.ASSESSMENT_FAILED, title="Тест не пройден", message=f"Результат по курсу «{assignment.course.title}»: {attempt.score_percent}%.", entity_type="AssessmentAttempt", entity_id=attempt.id, priority=Notification.Priority.WARNING)
    record(actor, "learning.assessment_graded", attempt, new_values={"score_percent": str(attempt.score_percent), "passed": attempt.passed}, request=request)
    return attempt


@transaction.atomic
def submit_attempt(*, attempt, actor, answers, request=None):
    if attempt.employee.user_id != actor.id:
        raise ValidationError("Отправить можно только собственную попытку")
    if attempt.status != AssessmentAttempt.Status.IN_PROGRESS:
        raise ValidationError("Попытка уже отправлена")
    elapsed = int((timezone.now() - attempt.started_at).total_seconds())
    if elapsed > attempt.assessment.time_limit_minutes * 60:
        attempt.status = AssessmentAttempt.Status.EXPIRED
        attempt.submitted_at = timezone.now()
        attempt.time_spent_seconds = elapsed
        attempt.save(update_fields=["status", "submitted_at", "time_spent_seconds"])
        raise ValidationError("Время прохождения теста истекло")
    answer_map = {int(item.get("question")): item for item in answers if item.get("question")}
    questions = list(attempt.questions.prefetch_related("options").all())
    missing = [q.id for q in questions if q.is_required and q.id not in answer_map]
    if missing:
        raise ValidationError({"answers": f"Ответьте на обязательные вопросы: {missing}"})
    manual = attempt.assessment.manual_review_required
    for question in questions:
        item = answer_map.get(question.id, {})
        response = AssessmentResponse.objects.create(attempt=attempt, question=question, text_answer=item.get("text_answer", ""), number_answer=item.get("number_answer"))
        selected_ids = item.get("selected_options", [])
        valid_ids = set(question.options.filter(id__in=selected_ids).values_list("id", flat=True))
        if len(valid_ids) != len(set(selected_ids)):
            raise ValidationError({"answers": f"Недопустимый вариант ответа для вопроса {question.id}"})
        response.selected_options.set(valid_ids)
        if not _auto_grade(response):
            manual = True
    attempt._prefetched_objects_cache.pop("responses", None)
    attempt.submitted_at = timezone.now()
    attempt.time_spent_seconds = elapsed
    attempt.status = AssessmentAttempt.Status.WAITING_REVIEW if manual else AssessmentAttempt.Status.AUTO_GRADED
    attempt.save(update_fields=["submitted_at", "time_spent_seconds", "status"])
    record(actor, "learning.assessment_submitted", attempt, request=request)
    return attempt if manual else _finalize_attempt(attempt, actor=actor, request=request)


@transaction.atomic
def review_attempt(*, attempt, reviewer, reviews, comment="", request=None):
    if attempt.status != AssessmentAttempt.Status.WAITING_REVIEW:
        raise ValidationError("Попытка не ожидает ручной проверки")
    for item in reviews:
        try:
            response = attempt.responses.get(pk=item.get("response"))
        except AssessmentResponse.DoesNotExist:
            raise ValidationError("Ответ не найден")
        points = Decimal(str(item.get("points_awarded", 0)))
        if points < 0 or points > response.question.points:
            raise ValidationError("Некорректное количество баллов")
        response.points_awarded = points
        response.is_correct = points == response.question.points
        response.review_comment = item.get("comment", "")
        response.save(update_fields=["points_awarded", "is_correct", "review_comment"])
    if attempt.responses.filter(is_correct__isnull=True).exists():
        raise ValidationError("Проверены не все открытые ответы")
    attempt._prefetched_objects_cache.pop("responses", None)
    attempt.reviewed_by = reviewer
    attempt.reviewed_at = timezone.now()
    attempt.review_comment = comment
    attempt.save(update_fields=["reviewed_by", "reviewed_at", "review_comment"])
    return _finalize_attempt(attempt, actor=reviewer, request=request)
