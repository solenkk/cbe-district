from django.urls import path
from . import views

urlpatterns = [
    path("", views.device_list, name="device_list"),
    path("new/", views.device_create, name="device_create"),
    path("<int:pk>/", views.device_detail, name="device_detail"),
    path("<int:pk>/history/", views.device_history, name="device_history"),
    path("<int:pk>/sleeve/", views.device_sleeve, name="device_sleeve"),
    path("<int:pk>/install-component/", views.device_install_component, name="device_install_component"),
    path("<int:pk>/remove-component/<int:component_pk>/", views.device_remove_component, name="device_remove_component"),
    path("<int:pk>/disposal/recommend/", views.disposal_recommendation_create, name="disposal_recommendation_create"),
    path("disposals/", views.disposal_recommendation_list, name="disposal_recommendation_list"),
    path("disposals/<int:pk>/review/", views.disposal_recommendation_review, name="disposal_recommendation_review"),
]