from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from access_control.models import EmployeeRole, Permission, Role, RolePermission
from organizations.models import OrgUnit
from .models import Employee, AssignmentTarget
from .onboarding_lifecycle import OnboardingService, OnboardingTemplateService
from .profile_services import ChangeRequestService
from .services import EmployeeService


class PeopleAcceptanceGapTests(TestCase):
    def test_explicit_template_assignment_does_not_cross_actor_scope(self):
        permission,_=Permission.objects.get_or_create(code='people.onboarding.assign')
        RolePermission.objects.create(role=self.role,permission=permission,scope='org_unit')
        outside=OnboardingTemplateService.create(actor_user=self.hr,name='Outside',scope='org_unit',org_unit=self.employee.org_unit)
        shared=OnboardingTemplateService.create(actor_user=self.hr,name='Shared')
        for template in (outside,shared):
            OnboardingTemplateService.publish(template=template,actor_user=self.hr,expected_version=1,
                steps=[{'key':'manual','title':'Manual','step_type':'manual'}])
            template.refresh_from_db()
        client=APIClient();client.force_authenticate(self.hr)
        path='/api/internal/v1/people/onboarding/'
        self.assertEqual(client.post(path,{'employee':str(self.reviewer.pk),'template':str(outside.pk)},format='json').status_code,404)
        self.assertEqual(client.post(path,{'employee':str(self.reviewer.pk),'template':str(shared.pk)},format='json').status_code,201)

    def test_scoped_template_creation_and_move_are_atomic(self):
        from .models import OnboardingTemplate
        from audit.models import AuditEvent
        from events.models import OutboxEvent
        for code,scope in [('people.onboarding_template.view','global'),('people.onboarding_template.create','org_unit'),('people.onboarding_template.update','org_unit')]:
            permission,_=Permission.objects.get_or_create(code=code)
            RolePermission.objects.create(role=self.role,permission=permission,scope=scope)
        client=APIClient();client.force_authenticate(self.hr)
        path='/api/internal/v1/people/onboarding-templates/'
        count=(OnboardingTemplate.objects.count(),AuditEvent.objects.count(),OutboxEvent.objects.count())
        for data in [{'name':'Forbidden global','scope':'global'},
                     {'name':'Forbidden outside','scope':'org_unit','org_unit':str(self.employee.org_unit_id)}]:
            self.assertEqual(client.post(path,data,format='json').status_code,403)
        self.assertEqual(count,(OnboardingTemplate.objects.count(),AuditEvent.objects.count(),OutboxEvent.objects.count()))
        response=client.post(path,{'name':'Allowed','scope':'org_unit','org_unit':str(self.reviewer.org_unit_id)},format='json')
        self.assertEqual(response.status_code,201)
        template=OnboardingTemplate.objects.get(pk=response.data['id'])
        response=client.patch(path+str(template.pk)+'/',{'version':template.version,'org_unit':str(self.employee.org_unit_id),'name':'Forbidden'},format='json')
        self.assertEqual(response.status_code,403)
        template.refresh_from_db();self.assertEqual(template.name,'Allowed');self.assertEqual(template.version,1)

    def test_template_visibility_excludes_expired_future_and_null_context(self):
        from datetime import timedelta
        from .onboarding_phase24_api import visible_templates
        code='people.onboarding_template.view'
        permission,_=Permission.objects.get_or_create(code=code)
        RolePermission.objects.create(role=self.role,permission=permission,scope='org_unit')
        template=OnboardingTemplateService.create(actor_user=self.hr,name='Outside template',scope='org_unit',org_unit=self.employee.org_unit)
        self.assertFalse(visible_templates(self.hr,code).filter(pk=template.pk).exists())
        EmployeeRole.objects.filter(employee=self.reviewer).update(org_unit=self.employee.org_unit)
        self.assertTrue(visible_templates(self.hr,code).filter(pk=template.pk).exists())
        EmployeeRole.objects.filter(employee=self.reviewer).update(active_from=timezone.now()+timedelta(days=1))
        self.assertFalse(visible_templates(self.hr,code).exists())
        EmployeeRole.objects.filter(employee=self.reviewer).update(active_from=None,active_until=timezone.now()-timedelta(seconds=1))
        self.assertFalse(visible_templates(self.hr,code).exists())
        EmployeeRole.objects.filter(employee=self.reviewer).update(active_until=None,org_unit=None)
        self.reviewer.org_unit=None;self.reviewer.save(update_fields=['org_unit'])
        self.assertFalse(visible_templates(self.hr,code).filter(pk=template.pk).exists())

    def test_global_view_does_not_expand_scoped_onboarding_manage(self):
        for code,scope in [('people.onboarding.view','global'),('people.onboarding.manage','org_unit')]:
            permission,_=Permission.objects.get_or_create(code=code)
            RolePermission.objects.create(role=self.role,permission=permission,scope=scope)
        template=OnboardingTemplateService.create(actor_user=self.hr,name='Mixed scopes')
        OnboardingTemplateService.publish(template=template,actor_user=self.hr,expected_version=1,
            steps=[{'key':'manual','title':'Manual','step_type':'manual'}])
        template.refresh_from_db()
        instance=OnboardingService.assign(employee=self.employee,actor_user=self.hr,template=template)
        client=APIClient();client.force_authenticate(self.hr)
        path=f'/api/internal/v1/people/onboarding/{instance.pk}/'
        self.assertEqual(client.get(path).status_code,200)
        self.assertEqual(client.post(path+'start/',{'version':instance.version},format='json').status_code,404)
        instance.refresh_from_db();self.assertEqual(instance.status,'pending');self.assertEqual(instance.version,1)

    def setUp(self):
        self.user = get_user_model().objects.create_user(username='gap-user', email='gap-user@example.test')
        self.employee = Employee.objects.create(user=self.user, first_name='Synthetic', org_unit=OrgUnit.objects.create(name='A'))
        self.hr = get_user_model().objects.create_user(username='gap-hr', email='gap-hr@example.test')
        self.reviewer = Employee.objects.create(user=self.hr, first_name='Outside', org_unit=OrgUnit.objects.create(name='B'))
        permission, _ = Permission.objects.get_or_create(code='people.change_request.review')
        self.role = Role.objects.create(code='gap-reviewer', name='Scoped synthetic reviewer')
        RolePermission.objects.create(role=self.role, permission=permission, scope='org_unit')
        EmployeeRole.objects.create(employee=self.reviewer, role=self.role, org_unit=self.reviewer.org_unit)

    def test_outside_hr_cannot_read_or_review_change_request(self):
        item = ChangeRequestService.submit(self.employee,self.user,'work_phone',{'value':'+70000000001'},'Synthetic')
        client=APIClient();client.force_authenticate(self.hr)
        path=f'/api/internal/v1/people/change-requests/{item.pk}/'
        self.assertEqual(client.get(path).status_code,404)
        self.assertEqual(client.post(path+'approve/',{'version':item.version}).status_code,404)
        item.refresh_from_db();self.assertEqual(item.status,'submitted')

    def test_self_restore_without_permission_returns_404_not_500(self):
        client=APIClient();client.raise_request_exception=False;client.force_authenticate(self.user)
        response=client.post(f'/api/internal/v1/people/{self.employee.pk}/access/restore/',{})
        self.assertIn(response.status_code,(403,404))

    def test_termination_revokes_roles_and_rehire_does_not_restore_them(self):
        assignment=EmployeeRole.objects.create(employee=self.employee,role=self.role,org_unit=self.employee.org_unit)
        EmployeeService.terminate(employee=self.employee,actor_user=self.hr)
        EmployeeService.reactivate(employee=self.employee,actor_user=self.hr)
        assignment.refresh_from_db();self.assertFalse(assignment.is_active)

    def test_worker_completes_only_final_work_task_once(self):
        from work_tasks.models import TaskTemplate,Task
        from events.models import OutboxEvent
        setup=get_user_model().objects.create_superuser(username='gap-setup',email='gap-setup@example.test')
        target=AssignmentTarget.objects.create(target_type='employee',employee=self.employee)
        work=TaskTemplate.objects.create(name='Synthetic',task_title='Synthetic',responsible_target=target,created_by=self.employee)
        template=OnboardingTemplateService.create(actor_user=setup,name='Synthetic')
        OnboardingTemplateService.publish(template=template,actor_user=setup,expected_version=1,steps=[{'key':'task','title':'Task','step_type':'task','task_template':work}])
        template.refresh_from_db()
        instance=OnboardingService.assign(employee=self.employee,actor_user=setup,template=template)
        step=instance.steps.get()
        task=OnboardingService.create_task(step=step,actor_employee=self.employee,actor_user=setup)
        Task.objects.filter(pk=task.pk).update(status='review')
        call_command('process_onboarding');step.refresh_from_db();self.assertNotEqual(step.status,'completed')
        Task.objects.filter(pk=task.pk).update(status='completed',completed_at=timezone.now())
        call_command('process_onboarding');step.refresh_from_db();self.assertEqual(step.status,'completed')
        version=step.version;count=OutboxEvent.objects.count()
        call_command('process_onboarding');step.refresh_from_db();self.assertEqual(step.version,version)
        self.assertEqual(OutboxEvent.objects.count(),count)

    def test_directory_null_scope_does_not_match_unassigned_people(self):
        from .onboarding_api import visible_employees
        self.employee.org_unit = None; self.employee.save(update_fields=['org_unit'])
        self.reviewer.org_unit = None; self.reviewer.save(update_fields=['org_unit'])
        grant = EmployeeRole.objects.get(employee=self.reviewer)
        grant.org_unit = None; grant.save(update_fields=['org_unit'])
        self.assertFalse(visible_employees(self.hr, 'people.change_request.review').filter(pk=self.employee.pk).exists())

    def test_expired_directory_grant_is_not_used(self):
        from datetime import timedelta
        from .onboarding_api import visible_employees
        RolePermission.objects.filter(role=self.role).update(scope='global')
        EmployeeRole.objects.filter(employee=self.reviewer).update(active_until=timezone.now()-timedelta(seconds=1))
        self.assertFalse(visible_employees(self.hr, 'people.change_request.review').exists())

    def test_no_manager_is_not_a_shared_team_or_organization(self):
        from access_control.policies import EmployeeAccessPolicy
        from .models import EmployeeProfile
        from .profile_services import can_see
        grant = EmployeeRole.objects.get(employee=self.reviewer)
        self.assertFalse(EmployeeAccessPolicy.allows(actor=self.reviewer,target=self.employee,grant=grant,scope='team'))
        profile = EmployeeProfile.objects.create(employee=self.employee, additional_email_visibility='organization')
        self.assertFalse(can_see(profile,'additional_email',self.hr,self.employee))

    def test_published_onboarding_history_rejects_model_edits(self):
        from django.core.exceptions import ValidationError
        template = OnboardingTemplateService.create(actor_user=self.hr, name='Immutable synthetic')
        version = OnboardingTemplateService.publish(template=template, actor_user=self.hr, expected_version=1,
            steps=[{'key':'one','title':'Original','step_type':'manual'}])
        version.name_snapshot = 'Changed'
        with self.assertRaises(ValidationError): version.save()
        step=version.steps.get();step.title='Changed'
        with self.assertRaises(ValidationError): step.save()
        with self.assertRaises(ValidationError): step.delete()
        from django.contrib import admin
        from .models import OnboardingTemplateStep
        self.assertIn('dependencies',admin.site._registry[OnboardingTemplateStep].readonly_fields)

    def test_scoped_reviewer_values_stay_masked_without_sensitive_permission(self):
        EmployeeRole.objects.filter(employee=self.reviewer).update(org_unit=self.employee.org_unit)
        item=ChangeRequestService.submit(self.employee,self.user,'work_phone',{'value':'+70000000001'},'Synthetic')
        client=APIClient();client.force_authenticate(self.hr)
        response=client.get(f'/api/internal/v1/people/change-requests/{item.pk}/')
        self.assertEqual(response.status_code,200)
        # User-approved rule: review alone does not disclose the submitted value.
        self.assertEqual(response.data['requested_value'],{'masked':True})

    def test_change_request_values_require_review_and_sensitive_in_scope(self):
        EmployeeRole.objects.filter(employee=self.reviewer).update(org_unit=self.employee.org_unit)
        permission,_=Permission.objects.get_or_create(code='people.profile.view_sensitive')
        RolePermission.objects.create(role=self.role,permission=permission,scope='org_unit')
        item=ChangeRequestService.submit(self.employee,self.user,'work_phone',{'value':'+70000000001'},'Synthetic')
        client=APIClient();client.force_authenticate(self.hr)
        path=f'/api/internal/v1/people/change-requests/{item.pk}/'
        response=client.get(path)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.data['requested_value'],{'value':'+70000000001'})
        EmployeeRole.objects.filter(employee=self.reviewer).update(org_unit=self.reviewer.org_unit)
        self.assertEqual(client.get(path).status_code,404)

    def test_manual_resolve_cannot_bypass_dependencies(self):
        for code in ['people.onboarding.view','people.onboarding.manage']:
            permission,_=Permission.objects.get_or_create(code=code)
            RolePermission.objects.create(role=self.role,permission=permission,scope='global')
        template=OnboardingTemplateService.create(actor_user=self.hr,name='Resolve dependency')
        OnboardingTemplateService.publish(template=template,actor_user=self.hr,expected_version=1,steps=[
            {'key':'first','title':'First','step_type':'manual'},
            {'key':'second','title':'Second','step_type':'manual','dependencies':['first']},
        ])
        template.refresh_from_db()
        instance=OnboardingService.assign(employee=self.employee,actor_user=self.hr,template=template)
        step=instance.steps.get(template_step__key='second')
        client=APIClient();client.force_authenticate(self.hr)
        response=client.post(f'/api/internal/v1/people/onboarding/{instance.pk}/steps/{step.pk}/resolve/',{'version':step.version},format='json')
        self.assertEqual(response.status_code,200)
        step.refresh_from_db();self.assertEqual(step.status,'blocked')
