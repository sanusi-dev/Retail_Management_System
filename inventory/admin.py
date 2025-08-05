from django.contrib import admin
from django.apps import apps
from django.db import models


app_models = apps.get_app_config('inventory').get_models()
for model in app_models:
    admin.site.register(model)