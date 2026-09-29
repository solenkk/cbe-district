from django.urls import path
from . import views

urlpatterns = [
    path("", views.component_list, name="component_list"),
    path("new/", views.component_create, name="component_create"),
]
