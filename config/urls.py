from django.contrib import admin
from django.urls import path
from django.views.generic import TemplateView
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from planner.views import RoutePlanView

urlpatterns = [
    path("", TemplateView.as_view(template_name="planner/index.html"), name="home"),
    path("api/route/", RoutePlanView.as_view(), name="route-plan"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    path("admin/", admin.site.urls),
]
