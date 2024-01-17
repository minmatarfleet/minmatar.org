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
from discord import views
from django.urls import path

urlpatterns = [
    path("login", views.discord_login, name="oauth-login"),
    path("logout", views.discord_logout, name="oauth-logout"),
    path(
        "login/redirect",
        views.discord_login_redirect,
        name="discord-login-redirect",
    ),
]
