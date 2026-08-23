from datetime import datetime, timezone
from django.test import TestCase
from rest_framework.test import APIClient
from accounts.models import User
from access_control.models import Permission, Role, RolePermission, EmployeeRole, Scope
from audit.models import AuditEvent
from events.models import OutboxEvent
from employees.models import Employee
from organizations.models import LegalEntity, OrgUnit, Location
from .models import ServiceCategory, Service, RequestType, RequestFieldDefinition, RequestFieldOption, RequestTypeAccessRule, AccessScope, FieldType
from .services import CategoryService, CatalogError, SchemaService, RequestSchemaValidator, RequestTypeAccessPolicy


class CatalogTestCase(TestCase):
    def setUp(self):
        self.user=User.objects.create_superuser(username="catalog-admin",password="pass")
        self.le=LegalEntity.objects.create(name="LE")
        self.unit=OrgUnit.objects.create(name="Unit",legal_entity=self.le)
        self.location=Location.objects.create(name="Office",legal_entity=self.le)
        self.actor=Employee.objects.create(user=self.user,first_name="Admin",legal_entity=self.le,org_unit=self.unit,primary_location=self.location)
        self.category=ServiceCategory.objects.create(name="IT")
        self.service=Service.objects.create(category=self.category,name="IT Support",owner_org_unit=self.unit)
        self.rt=RequestType.objects.create(service=self.service,name="Equipment failure",code="IT_EQUIPMENT_FAILURE",created_by=self.actor)

    def field(self,**kw):
        data={"request_type":self.rt,"key":"description","label":"Description","field_type":FieldType.TEXT,"required":True}; data.update(kw); return RequestFieldDefinition.objects.create(**data)

    def test_category_tree_rejects_self_and_cycles_and_moves(self):
        child=ServiceCategory.objects.create(name="Hardware",parent=self.category)
        with self.assertRaises(CatalogError): CategoryService.validate_parent(self.category,self.category)
        with self.assertRaises(CatalogError): CategoryService.validate_parent(self.category,child)
        child=CategoryService.move(child,None,self.actor,self.user); self.assertIsNone(child.parent)

    def test_service_and_type_effective_availability(self):
        self.field(); SchemaService.publish(self.rt,self.actor,self.user)
        self.assertTrue(RequestTypeAccessPolicy.allows(self.rt,self.actor,self.user))
        self.service.is_active=False; self.service.save(update_fields=["is_active"])
        response=APIClient(); response.force_authenticate(self.user)
        self.assertEqual(response.get(f"/api/internal/v1/request-types/{self.rt.pk}/form-schema/").status_code,404)

    def test_publish_versions_are_immutable_snapshots(self):
        field=self.field(); one=SchemaService.publish(self.rt,self.actor,self.user)
        field.label="Changed"; field.save(); two=SchemaService.publish(self.rt,self.actor,self.user)
        self.assertEqual(one.schema_json["fields"][0]["label"],"Description")
        self.assertEqual(two.version,2)
        one.schema_json={};
        with self.assertRaises(Exception): one.save()
        self.assertEqual(AuditEvent.objects.filter(action="request_type.schema_published").count(),2)
        self.assertEqual(OutboxEvent.objects.filter(event_type="request_type.schema_published").count(),2)

    def test_all_field_types_and_validation(self):
        fields=[
            ("text",FieldType.TEXT,{"min_length":2},"ok"),("area",FieldType.TEXTAREA,{},"body"),("integer",FieldType.INTEGER,{"min_value":1},2),
            ("decimal",FieldType.DECIMAL,{"max_value":"10.5"},"2.25"),("boolean",FieldType.BOOLEAN,{},True),("date",FieldType.DATE,{},"2026-08-15"),
            ("datetime",FieldType.DATETIME,{},"2026-08-15T10:00:00+07:00"),("employee",FieldType.EMPLOYEE,{"same_legal_entity":True},str(self.actor.pk)),
            ("org",FieldType.ORG_UNIT,{},str(self.unit.pk)),("entity",FieldType.LEGAL_ENTITY,{},str(self.le.pk)),("location",FieldType.LOCATION,{},str(self.location.pk)),("file",FieldType.FILE,{},"file-token")]
        payload={}
        for pos,(key,t,config,value) in enumerate(fields): self.field(key=key,label=key,field_type=t,config=config,position=pos); payload[key]=value
        choice=self.field(key="choice",label="Choice",field_type=FieldType.CHOICE); RequestFieldOption.objects.create(field=choice,value="A",label="A"); payload["choice"]="A"
        multi=self.field(key="multi",label="Multi",field_type=FieldType.MULTI_CHOICE); RequestFieldOption.objects.create(field=multi,value="A",label="A"); payload["multi"]=["A"]
        schema=SchemaService.publish(self.rt,self.actor,self.user)
        cleaned=RequestSchemaValidator.validate(schema,payload,self.actor); self.assertEqual(cleaned["decimal"],"2.25")
        payload["choice"]="UNKNOWN"
        with self.assertRaises(CatalogError): RequestSchemaValidator.validate(schema,payload,self.actor)

    def test_conditional_required_hidden_value_is_not_saved(self):
        reason=self.field(key="reason",label="Reason",field_type=FieldType.CHOICE,required=False); RequestFieldOption.objects.create(field=reason,value="OTHER",label="Other"); RequestFieldOption.objects.create(field=reason,value="KNOWN",label="Known")
        self.field(key="other",label="Other",config={"visible_if":{"field":"reason","operator":"EQUALS","value":"OTHER"}})
        schema=SchemaService.publish(self.rt,self.actor,self.user)
        cleaned=RequestSchemaValidator.validate(schema,{"reason":"KNOWN","other":"discard"},self.actor); self.assertNotIn("other",cleaned)
        with self.assertRaises(CatalogError): RequestSchemaValidator.validate(schema,{"reason":"OTHER"},self.actor)

    def test_access_rules_all_scopes(self):
        self.field(); SchemaService.publish(self.rt,self.actor,self.user)
        for scope,kw in ((AccessScope.GLOBAL,{}),(AccessScope.LEGAL_ENTITY,{"legal_entity":self.le}),(AccessScope.ORG_UNIT,{"org_unit":self.unit}),(AccessScope.LOCATION,{"location":self.location})):
            self.rt.access_rules.all().delete(); RequestTypeAccessRule.objects.create(request_type=self.rt,scope_type=scope,**kw); self.assertTrue(RequestTypeAccessPolicy.allows(self.rt,self.actor,self.user))
        role=Role.objects.create(code="requester",name="Requester"); EmployeeRole.objects.create(employee=self.actor,role=role)
        self.rt.access_rules.all().delete(); RequestTypeAccessRule.objects.create(request_type=self.rt,scope_type=AccessScope.ROLE,role=role); self.assertTrue(RequestTypeAccessPolicy.allows(self.rt,self.actor,self.user))

    def test_management_and_user_api(self):
        client=APIClient(); client.force_authenticate(self.user)
        response=client.post(f"/api/internal/v1/request-types/{self.rt.pk}/fields/",{"key":"summary","label":"Summary","field_type":"text","required":True},format="json"); self.assertEqual(response.status_code,201,response.data)
        response=client.post(f"/api/internal/v1/request-types/{self.rt.pk}/publish-schema/",{},format="json"); self.assertEqual(response.status_code,201,response.data)
        self.assertEqual(client.get("/api/internal/v1/service-catalog/").status_code,200)
        self.assertEqual(client.get(f"/api/internal/v1/request-types/{self.rt.pk}/form-schema/").status_code,200)


class CatalogPermissionTests(TestCase):
    def test_direct_access_without_permission_is_hidden(self):
        user=User.objects.create_user(username="plain",email="plain@catalog.test")
        actor=Employee.objects.create(user=user,first_name="Plain")
        admin_user=User.objects.create_superuser(username="publisher",email="publisher@catalog.test")
        admin=Employee.objects.create(user=admin_user,first_name="Admin")
        cat=ServiceCategory.objects.create(name="IT"); service=Service.objects.create(category=cat,name="IT")
        rt=RequestType.objects.create(service=service,name="Hidden",code="HIDDEN",created_by=admin)
        RequestFieldDefinition.objects.create(request_type=rt,key="x",label="X",field_type=FieldType.TEXT)
        SchemaService.publish(rt,admin,admin_user)
        client=APIClient(); client.force_authenticate(user)
        self.assertEqual(client.get(f"/api/internal/v1/request-types/{rt.pk}/form-schema/").status_code,404)
        permission=Permission.objects.create(code="request.create",name="Create request"); role=Role.objects.create(code="employee",name="Employee")
        RolePermission.objects.create(role=role,permission=permission,scope=Scope.GLOBAL); EmployeeRole.objects.create(employee=actor,role=role)
        self.assertEqual(client.get(f"/api/internal/v1/request-types/{rt.pk}/form-schema/").status_code,200)
        other=LegalEntity.objects.create(name="Other"); RequestTypeAccessRule.objects.create(request_type=rt,scope_type=AccessScope.LEGAL_ENTITY,legal_entity=other)
        self.assertEqual(client.get(f"/api/internal/v1/request-types/{rt.pk}/form-schema/").status_code,404)
