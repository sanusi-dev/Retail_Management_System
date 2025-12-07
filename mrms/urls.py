from django.contrib import admin
from django.urls import path, include
from django.conf import settings


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("account.urls")),
    path("", include("core.urls")),
    path("customer/", include("customer.urls")),
    path("inventory/", include("inventory.urls")),
    path("", include("loan.urls")),
    path("purchases/", include("supply_chain.urls")),
]

if settings.DEBUG:
    urlpatterns += [
        path("__reload__/", include("django_browser_reload.urls")),
    ]
