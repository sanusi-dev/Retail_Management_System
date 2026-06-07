from django.contrib import admin
from django.urls import path, include


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("account.urls")),
    path("", include("core.urls")),
    path("customer/", include("customer.urls")),
    path("inventory/", include("inventory.urls")),
    path("purchases/", include("supply_chain.urls")),
]
