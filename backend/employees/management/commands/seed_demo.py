from datetime import date
from django.core.management.base import BaseCommand
from django.db import transaction
from accounts.models import Role, User, UserRole
from employees.models import Employee, EmployeeFacility
from organizations.models import Cluster, Company, Department, Facility, Region, Zone
from tasks.models import Task, TaskComment, TaskHistory
from checklists.models import ChecklistQuestion, ChecklistRun, ChecklistTemplate
from sensors.models import Sensor
from sensors.models import SensorEvent
from incidents.models import Incident, IncidentHistory
from notifications.models import Notification
from knowledge_base.models import KnowledgeCategory, KnowledgeMaterial, MaterialAcknowledgmentAssignment, MaterialFavorite, MaterialTag, MaterialVersion, TTKMetadata
from learning.models import AnswerOption, Assessment, Certificate, Course, CourseAssignment, CourseCategory, CourseModule, Lesson, LessonProgress, Question
from learning.integrations import provision_course_assignment
from django.utils import timezone
from datetime import timedelta

class Command(BaseCommand):
    help = "Создаёт вымышленные демонстрационные данные AYS Connect"

    @transaction.atomic
    def handle(self, *args, **options):
        roles = {}
        for code, label in Role.Code.choices:
            roles[code], _ = Role.objects.update_or_create(code=code, defaults={"name": label})
        company, _ = Company.objects.update_or_create(short_name="AYS Demo", defaults={"name": "AYS Hospitality — демонстрационная компания", "description": "Вымышленная компания для презентации платформы", "is_demo": True})
        region, _ = Region.objects.get_or_create(company=company, name="Сибирь")
        cluster, _ = Cluster.objects.get_or_create(region=region, name="Новосибирск")
        facility, _ = Facility.objects.update_or_create(cluster=cluster, name="Ресторан «Север» (демо)", defaults={"facility_type": Facility.Type.RESTAURANT, "address": "Демонстрационный адрес, 10", "work_schedule": "Ежедневно, 08:00–00:00", "description": "Учебный объект без реальных данных", "is_demo": True})
        for zone in ("Кухня", "Бар", "Склад", "Зал"):
            Zone.objects.get_or_create(facility=facility, name=zone)
        operations, _ = Department.objects.get_or_create(company=company, name="Операционная служба")
        tech, _ = Department.objects.get_or_create(company=company, name="Техническая служба")

        manager_user, created = User.objects.get_or_create(email="manager@demo.ays-connect.local", defaults={"username": "demo_manager", "first_name": "Анна", "last_name": "Петрова", "middle_name": "Игоревна", "phone": "+7 900 000-00-02", "is_demo": True})
        if created: manager_user.set_password("Demo12345!"); manager_user.save()
        manager, _ = Employee.objects.update_or_create(user=manager_user, defaults={"company": company, "department": operations, "employee_number": "DEMO-0001", "position": "Управляющий объектом", "hire_date": date(2023, 4, 10), "skills": ["Управление командой", "Операционный контроль"], "is_demo": True})
        EmployeeFacility.objects.get_or_create(employee=manager, facility=facility, defaults={"is_primary": True})
        UserRole.objects.get_or_create(user=manager_user, role=roles[Role.Code.FACILITY_MANAGER], company=company, facility=facility)

        ivan_user, created = User.objects.get_or_create(email="ivan@demo.ays-connect.local", defaults={"username": "demo_ivan", "first_name": "Иван", "last_name": "Соколов", "middle_name": "Алексеевич", "phone": "+7 900 000-00-01", "is_demo": True})
        if created: ivan_user.set_password("Demo12345!"); ivan_user.save()
        ivan, _ = Employee.objects.update_or_create(user=ivan_user, defaults={"company": company, "department": tech, "manager": manager, "employee_number": "DEMO-0042", "position": "Технический специалист", "hire_date": date(2024, 2, 12), "work_schedule": "2/2, 08:00–20:00", "skills": ["Эксплуатация оборудования", "Охрана труда", "Первая помощь"], "is_demo": True})
        EmployeeFacility.objects.get_or_create(employee=ivan, facility=facility, defaults={"is_primary": True})
        UserRole.objects.get_or_create(user=ivan_user, role=roles[Role.Code.TECHNICIAN], company=company, facility=facility)
        now = timezone.now()
        demo_tasks = [
            ("Проверить вентиляцию в зоне кухни", Task.Priority.HIGH, Task.Status.ASSIGNED, 2, "Техническое обслуживание"),
            ("Ежедневный осмотр технических помещений", Task.Priority.NORMAL, Task.Status.ACCEPTED, 5, "Регламентный осмотр"),
            ("Заменить фильтр системы водоочистки", Task.Priority.HIGH, Task.Status.IN_PROGRESS, 10, "Ремонт"),
            ("Передать смену и заполнить журнал", Task.Priority.NORMAL, Task.Status.ASSIGNED, 12, "Операционная задача"),
            ("Проверить резервное питание серверной", Task.Priority.CRITICAL, Task.Status.REVIEW, -2, "IT-инфраструктура"),
            ("Инвентаризация расходных материалов", Task.Priority.LOW, Task.Status.WAITING, 30, "Учёт"),
        ]
        for index, (title, priority, task_status, hours, category) in enumerate(demo_tasks, 1):
            deadline = now + timedelta(hours=hours)
            task, created_task = Task.objects.get_or_create(title=title, assignee=ivan_user, is_demo=True, defaults={"description": f"Демонстрационная задача: {title.lower()}.", "creator": manager_user, "facility": facility, "department": tech, "zone": Zone.objects.filter(facility=facility).first(), "category": category, "priority": priority, "status": task_status, "initial_deadline": deadline, "deadline": deadline, "acceptance_criteria": "Выполнить работу и описать результат", "requires_review": True, "requires_comment": True, "estimated_minutes": 30 + index * 10, "source": Task.Source.MANUAL})
            if created_task:
                TaskHistory.objects.create(task=task, actor=manager_user, action="created", to_status=task_status)
        review_task = Task.objects.get(title="Проверить резервное питание серверной", is_demo=True)
        TaskComment.objects.get_or_create(task=review_task, author=ivan_user, text="Проверка выполнена, резервный ввод срабатывает штатно.")
        haccp, _ = ChecklistTemplate.objects.update_or_create(name="Открытие смены — санитарный контроль", facility=facility, defaults={"category":"Открытие смены","description":"Ежедневная проверка критических санитарных точек","frequency":ChecklistTemplate.Frequency.DAILY,"is_mandatory":True,"is_haccp":True,"is_demo":True})
        questions=[("Рабочие поверхности чистые",ChecklistQuestion.Type.BOOLEAN,None,None),("Температура холодильной камеры, °C",ChecklistQuestion.Type.TEMPERATURE,-2,6),("Маркировка продукции соответствует требованиям",ChecklistQuestion.Type.BOOLEAN,None,None),("Комментарий ответственного",ChecklistQuestion.Type.TEXT,None,None)]
        for order,(text,qtype,min_v,max_v) in enumerate(questions,1): ChecklistQuestion.objects.update_or_create(template=haccp,order=order,defaults={"text":text,"question_type":qtype,"is_required":True,"min_value":min_v,"max_value":max_v})
        if not ChecklistRun.objects.filter(template=haccp,assignee=ivan_user,status=ChecklistRun.Status.ASSIGNED).exists(): ChecklistRun.objects.create(template=haccp,assignee=ivan_user,facility=facility,zone=Zone.objects.filter(facility=facility,name="Кухня").first(),due_at=now+timedelta(hours=3),is_demo=True)
        sensor, _ = Sensor.objects.update_or_create(serial_number="DEMO-TEMP-001",defaults={"name":"Холодильная камера №1","sensor_type":Sensor.Type.TEMPERATURE,"manufacturer":"AYS Demo Devices","model":"T-100","facility":facility,"zone":Zone.objects.filter(facility=facility,name="Кухня").first(),"equipment":"Холодильная камера","unit":"°C","allowed_min":0,"allowed_max":6,"critical_min":-5,"critical_max":10,"installed_at":date(2026,1,15),"responsible":ivan_user,"battery_level":78,"signal_quality":92,"is_demo":True})
        if not Incident.objects.filter(sensor=sensor,status__in=[Incident.Status.NOTIFIED,Incident.Status.ACKNOWLEDGED,Incident.Status.ESCALATED]).exists():
            event=SensorEvent.objects.create(sensor=sensor,level=Sensor.State.CRITICAL,started_at=now-timedelta(minutes=18),peak_value=12.4)
            incident=Incident.objects.create(sensor=sensor,sensor_event=event,deviation_type="Превышение температуры",level=Sensor.State.CRITICAL,started_at=event.started_at,peak_value=12.4,responsible=ivan_user,notified_at=now-timedelta(minutes=17),status=Incident.Status.NOTIFIED,is_demo=True)
            IncidentHistory.objects.create(incident=incident,action="created",details={"source":"demo_sensor"})
        demo_notifications=[("Критическое отклонение температуры","Холодильная камера №1: зафиксировано 12,4 °C",Notification.Type.INCIDENT,Notification.Priority.CRITICAL),("Новая задача назначена","Проверьте вентиляцию в зоне кухни",Notification.Type.TASK,Notification.Priority.WARNING),("Чек-лист ожидает прохождения","Открытие смены — санитарный контроль",Notification.Type.CHECKLIST,Notification.Priority.INFO)]
        for title,message,kind,priority in demo_notifications:Notification.objects.get_or_create(recipient=ivan_user,title=title,is_demo=True,defaults={"message":message,"notification_type":kind,"priority":priority,"telegram_status":"mock_sent"})
        knowledge_categories = {}
        for name, slug in (("Регламенты", "regulations"), ("Техническая служба", "technical"), ("ХАССП", "haccp"), ("ТТК", "ttk")):
            knowledge_categories[slug], _ = KnowledgeCategory.objects.update_or_create(slug=slug, defaults={"name": name, "is_active": True})
        tag_safety, _ = MaterialTag.objects.get_or_create(slug="safety", defaults={"name": "Безопасность"})
        tag_daily, _ = MaterialTag.objects.get_or_create(slug="daily-work", defaults={"name": "Ежедневная работа"})
        demo_materials = [
            ("Регламент реагирования на температурные отклонения", "temperature-incidents", KnowledgeMaterial.Type.REGULATION, "regulations", "Порядок действий при выходе температуры за допустимые пределы.", True, True),
            ("Инструкция работы с техническими заявками", "technical-requests", KnowledgeMaterial.Type.INSTRUCTION, "technical", "Приём, диагностика, эскалация и закрытие технических обращений.", True, False),
            ("Презентация по AYS Connect", "ays-connect-presentation", KnowledgeMaterial.Type.PRESENTATION, "technical", "Краткое знакомство с основными рабочими разделами платформы.", False, True),
            ("Основы системы ХАССП", "haccp-basics", KnowledgeMaterial.Type.HACCP, "haccp", "Контроль критических точек и действия при выявлении нарушения.", True, False),
            ("Техническое обслуживание холодильного оборудования", "refrigeration-maintenance", KnowledgeMaterial.Type.TECHNICAL_DOCUMENTATION, "technical", "Периодичность осмотров и безопасное обслуживание оборудования.", False, False),
            ("ТТК: Салат фирменный", "ttk-signature-salad", KnowledgeMaterial.Type.TTK, "ttk", "Демонстрационная технологическая карта блюда.", False, True),
        ]
        for index, (title, slug, kind, category_slug, description, required_flag, featured) in enumerate(demo_materials, 1):
            material, _ = KnowledgeMaterial.objects.update_or_create(slug=slug, defaults={"title": title, "description": description, "material_type": kind, "category": knowledge_categories[category_slug], "owner": manager_user, "owner_department": operations if kind in {KnowledgeMaterial.Type.REGULATION, KnowledgeMaterial.Type.HACCP, KnowledgeMaterial.Type.TTK} else tech, "status": KnowledgeMaterial.Status.PUBLISHED, "is_required": required_flag, "is_featured": featured, "published_at": now})
            version, _ = MaterialVersion.objects.get_or_create(material=material, version=1, defaults={"title": title, "content": f"{description}\n\nМатериал подготовлен для демонстрации базы знаний AYS Connect. Следуйте утверждённому порядку и при необходимости обратитесь к руководителю.", "change_summary": "Первая публикация", "created_by": manager_user, "effective_from": now, "is_current": True})
            if material.current_version_id != version.id:
                material.current_version = version; material.save(update_fields=["current_version"])
            material.tags.add(tag_daily, *([tag_safety] if required_flag else []))
            if kind == KnowledgeMaterial.Type.TTK:
                TTKMetadata.objects.update_or_create(material=material, defaults={"dish_name": "Салат фирменный", "dish_category": "Салаты", "brand": "AYS Hospitality", "facility": facility, "workshop": "Холодный цех", "output_weight": 250, "yield_unit": "г", "cooking_time_minutes": 15, "storage_temperature": "+2…+6 °C", "storage_duration": "12 часов", "ingredients": ["овощи", "зелень", "заправка"], "technology": "Подготовить ингредиенты, смешать и оформить перед подачей.", "allergens": [], "serving_requirements": "Подавать охлаждённым", "approved_by": manager_user, "effective_from": now})
            if index in {1, 2}:
                MaterialAcknowledgmentAssignment.objects.get_or_create(version=version, employee=ivan, defaults={"assigned_by": manager_user, "due_at": now + timedelta(days=index + 1)})
            if index in {3, 5}:
                MaterialFavorite.objects.get_or_create(material=material, employee=ivan)
        learning_categories = {}
        for name, slug in (("ХАССП", "learning-haccp"), ("Техническая служба", "learning-technical"), ("IT", "learning-it"), ("Корпоративные стандарты", "learning-standards")):
            learning_categories[slug], _ = CourseCategory.objects.update_or_create(slug=slug, defaults={"name": name, "is_active": True})
        demo_courses = [
            ("Работа с температурными инцидентами", "temperature-incident-course", "learning-haccp", "Реагирование на отклонения показаний датчиков.", True),
            ("Основы ХАССП", "haccp-course", "learning-haccp", "Критические контрольные точки и санитарные требования.", True),
            ("Регламент обработки технических обращений", "technical-requests-course", "learning-technical", "Диагностика и сопровождение технических заявок.", True),
            ("Информационная безопасность", "information-security-course", "learning-it", "Основные правила защиты корпоративных данных.", False),
            ("Работа с кассовым оборудованием", "cash-equipment-course", "learning-technical", "Безопасная эксплуатация и первичная диагностика касс.", False),
        ]
        seeded_courses = []
        for index, (title, slug, category_slug, description, mandatory) in enumerate(demo_courses, 1):
            course, _ = Course.objects.update_or_create(slug=slug, defaults={"title": title, "description": description, "short_description": description, "category": learning_categories[category_slug], "author": manager_user, "owner_department": tech, "is_mandatory": mandatory, "estimated_duration_minutes": 25 + index * 10, "passing_score": 80, "max_attempts": 3, "certificate_enabled": True, "certificate_validity_days": 365, "status": Course.Status.PUBLISHED, "published_at": now})
            module, _ = CourseModule.objects.update_or_create(course=course, sort_order=1, defaults={"title": "Основной модуль", "description": "Теория и практические правила", "is_required": True})
            lesson1, _ = Lesson.objects.update_or_create(module=module, sort_order=1, defaults={"title": "Основные положения", "lesson_type": Lesson.Type.TEXT, "content": f"{description}\n\nИзучите порядок действий и используйте его в ежедневной работе.", "estimated_duration_minutes": 15, "is_required": True})
            lesson2, _ = Lesson.objects.update_or_create(module=module, sort_order=2, defaults={"title": "Практические действия", "lesson_type": Lesson.Type.TEXT, "content": "Проверьте последовательность действий и подтвердите ознакомление.", "estimated_duration_minutes": 10, "is_required": True, "requires_confirmation": True})
            assessment, _ = Assessment.objects.update_or_create(course=course, title="Итоговый тест", defaults={"description": "Проверка усвоения основных положений", "time_limit_minutes": 10, "passing_score": 80, "max_attempts": 3, "shuffle_questions": False, "shuffle_answers": True, "is_active": True})
            demo_questions = [
                ("Какое действие выполняется первым?", Question.Type.SINGLE_CHOICE, [("Оценить ситуацию и открыть регламент", True), ("Игнорировать событие", False)]),
                ("Какие действия обязательны?", Question.Type.MULTIPLE_CHOICE, [("Зафиксировать событие", True), ("Уведомить ответственного", True), ("Скрыть отклонение", False)]),
                ("Нужно ли фиксировать результат?", Question.Type.TRUE_FALSE, [("Да", True), ("Нет", False)]),
                ("Укажите допустимое число пропущенных обязательных шагов", Question.Type.NUMBER, [("0", True)]),
                ("Кратко опишите порядок эскалации", Question.Type.TEXT, []),
            ]
            for question_index, (question_text, question_type, options) in enumerate(demo_questions, 1):
                question, _ = Question.objects.update_or_create(assessment=assessment, sort_order=question_index, defaults={"text": question_text, "question_type": question_type, "explanation": "Следуйте утверждённому регламенту.", "points": 1, "is_required": True, "manual_review_required": question_type == Question.Type.TEXT})
                for option_index, (option_text, is_correct) in enumerate(options, 1):
                    AnswerOption.objects.update_or_create(question=question, sort_order=option_index, defaults={"text": option_text, "match_key": option_text if question_type == Question.Type.NUMBER else "", "is_correct": is_correct})
            seeded_courses.append((course, lesson1, lesson2))
        assignment_states = [CourseAssignment.Status.WAITING_ASSESSMENT, CourseAssignment.Status.IN_PROGRESS, CourseAssignment.Status.OVERDUE, CourseAssignment.Status.COMPLETED, CourseAssignment.Status.COMPLETED]
        for index, ((course, lesson1, lesson2), assignment_status) in enumerate(zip(seeded_courses, assignment_states), 1):
            assignment, _ = CourseAssignment.objects.update_or_create(course=course, employee=ivan, source=CourseAssignment.Source.MANUAL, defaults={"assigned_by": manager_user, "due_at": now + timedelta(days=3-index) if assignment_status != CourseAssignment.Status.OVERDUE else now-timedelta(days=2), "status": assignment_status, "is_mandatory": course.is_mandatory, "progress_percent": 100 if assignment_status in {CourseAssignment.Status.WAITING_ASSESSMENT, CourseAssignment.Status.COMPLETED} else 50 if assignment_status == CourseAssignment.Status.IN_PROGRESS else 0, "started_at": now-timedelta(days=1) if assignment_status not in {CourseAssignment.Status.ASSIGNED, CourseAssignment.Status.OVERDUE} else None, "completed_at": now-timedelta(days=1) if assignment_status == CourseAssignment.Status.COMPLETED else None, "current_lesson": lesson2 if assignment_status == CourseAssignment.Status.IN_PROGRESS else None})
            provision_course_assignment(assignment, create_task=index in {1, 3})
            if assignment_status in {CourseAssignment.Status.WAITING_ASSESSMENT, CourseAssignment.Status.COMPLETED}:
                for lesson in (lesson1, lesson2):
                    LessonProgress.objects.update_or_create(assignment=assignment, lesson=lesson, defaults={"opened_at": now-timedelta(days=1), "completed_at": now-timedelta(days=1), "progress_percent": 100, "confirmed": True, "confirmed_at": now-timedelta(days=1), "time_spent_seconds": 600})
            if assignment_status == CourseAssignment.Status.COMPLETED:
                expires_in = 10 if index == 5 else 90
                Certificate.objects.get_or_create(assignment=assignment, defaults={"employee": ivan, "course": course, "certificate_number": f"AYS-DEMO-{assignment.id:06d}", "verification_code": f"demo-{assignment.id:08d}", "expires_at": now+timedelta(days=expires_in), "status": Certificate.Status.EXPIRING if expires_in <= 30 else Certificate.Status.ACTIVE, "issued_by": manager_user})
        self.stdout.write(self.style.SUCCESS("Демо-данные готовы. Вход: ivan@demo.ays-connect.local / Demo12345!"))
