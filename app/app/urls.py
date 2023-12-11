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
from django.contrib import admin
from django.urls import path
from discordlogin import views
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic.base import RedirectView
from home.views import index

urlpatterns = [
    path("", index, name="index"),
    path("admin/", admin.site.urls),
    path("oauth2", views.home, name="oauth2"),
    path("oauth2/login", views.discord_login, name="oauth_login"),
    path("oauth2/logout", views.discord_logout, name="oauth_logout"),
    path(
        "oauth2/login/redirect",
        views.discord_login_redirect,
        name="discord_login_redirect",
    ),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
