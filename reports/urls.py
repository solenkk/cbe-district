from django.urls import path
from . import views

urlpatterns = [
    path("", views.report_list, name="report_list"),
    path("<int:pk>/", views.report_detail, name="report_detail"),
    path("<int:pk>/export/", views.report_export, name="report_export"),
    path("<int:pk>/approve/", views.report_approve, name="report_approve"),
    path("audit/", views.dynamic_report, name="dynamic_report"),
    path("audit/export/", views.dynamic_report_export, name="dynamic_report_export"),
]