from django.urls import path

from . import views

app_name = "analytics"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("categorias/", views.categorias, name="categorias"),
    path("evolucao/", views.evolucao, name="evolucao"),
    path("tendencias/", views.tendencias, name="tendencias"),
    path("sazonalidade/", views.sazonalidade, name="sazonalidade"),
    path("assistente/", views.assistente, name="assistente"),
]
