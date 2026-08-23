from django.contrib import admin
from .models import Cluster, Company, Department, Facility, LegalEntity, Location, OrgUnit, Region, Zone
for model in (Company, Region, Cluster, Facility, Department, Zone, LegalEntity, OrgUnit, Location): admin.site.register(model)
