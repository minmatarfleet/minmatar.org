import ipaddress
from urllib.parse import urlsplit

from django.conf import settings
from django.http import HttpResponseRedirect
from django.shortcuts import redirect

from app.cors import allowed_origins

# Hosts that only reach the user's own machine: the desktop app's one-shot
# loopback listener (RFC 8252) and local development.
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}

# App deep links. Only an installed app receives these.
APP_SCHEMES = {"mobile", "minmatar"}

# Expo Go during mobile development: exp://<LAN IP>:8081/--/auth/callback.
EXPO_SCHEMES = {"exp", "exps"}


class DeepLinkRedirect(HttpResponseRedirect):
    allowed_schemes = ["http", "https", "mobile", "minmatar", "exp"]


def oauth_redirect(url: str):
    if "://" in url and not url.startswith(("http://", "https://")):
        return DeepLinkRedirect(url)
    return redirect(url)


def default_login_redirect_url() -> str:
    return f"{settings.WEB_LINK_URL.rstrip('/')}/auth/login"


def _website_origins() -> set[str]:
    origins = {o.lower() for o in allowed_origins()}
    web_link = urlsplit(settings.WEB_LINK_URL)
    origins.add(f"{web_link.scheme}://{web_link.netloc}".lower())
    return origins


def _is_local_network_host(host: str) -> bool:
    if host in LOOPBACK_HOSTS:
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return address.is_private or address.is_loopback


def is_allowed_login_redirect(url: str) -> bool:
    """
    True when a login may send its token to this URL.

    Logins append ?token=<JWT> to the redirect, so it must only ever point
    at our own website, the desktop app on this machine, or our mobile app.
    """
    if not isinstance(url, str) or not url:
        return False
    try:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
    except ValueError:
        return False
    scheme = parts.scheme.lower()

    if scheme in APP_SCHEMES:
        return True
    if scheme in EXPO_SCHEMES:
        return _is_local_network_host(host)
    if scheme not in ("http", "https") or not host:
        return False
    if parts.username or parts.password:
        return False
    if scheme == "http" and host in LOOPBACK_HOSTS:
        return True
    return f"{scheme}://{parts.netloc.lower()}" in _website_origins()


def safe_login_redirect_url(url: str, default: str) -> str:
    return url if is_allowed_login_redirect(url) else default
