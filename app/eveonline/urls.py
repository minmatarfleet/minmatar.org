"""
URL configuration for app project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path
from . import views

urlpatterns = [
    path("characters", views.list_characters, name="eveonline-characters"),
    path(
        "characters/add", views.add_character, name="eveonline-characters-add"
    ),
    path(
        "characters/add-alliance-character",
        views.add_alliance_character,
        name="eveonline-characters-add-alliance-character",
    ),
    path(
        "corporations", views.list_corporations, name="eveonline-corporations"
    ),
    path(
        "corporations/<int:corporation_pk>/update",
        views.update_corporation,
        name="eveonline-corporations-update",
    ),
    path(
        "corporations/<int:corporation_pk>/apply",
        views.create_corporation_application,
        name="eveonline-corporations-apply",
    ),
]
