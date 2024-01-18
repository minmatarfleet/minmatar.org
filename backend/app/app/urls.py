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
from authentication import router as auth_router
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from eveonline.router import router as eveonline_router
from ninja import NinjaAPI

from .views import index

api = NinjaAPI(title="Minmatar Fleet API", version="1.0.0")
api.add_router("auth/", auth_router)
api.add_router("eveonline/", eveonline_router)

urlpatterns = [
    path("", index, name="index"),
    path("api/", api.urls),
    path("admin/", admin.site.urls),
    path("sso/", include("esi.urls")),
    path("oauth2/", include("discord.urls")),
    path("eveonline/", include("eveonline.urls")),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
