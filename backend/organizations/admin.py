from django.contrib import admin
from .models import Cluster, Company, Department, Facility, Region, Zone
for model in (Company, Region, Cluster, Facility, Department, Zone): admin.site.register(model)
