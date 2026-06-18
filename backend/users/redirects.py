from django.http import HttpResponseRedirect
from django.shortcuts import redirect


class DeepLinkRedirect(HttpResponseRedirect):
    allowed_schemes = ["http", "https", "mobile", "minmatar", "exp"]


def oauth_redirect(url: str):
    if "://" in url and not url.startswith(("http://", "https://")):
        return DeepLinkRedirect(url)
    return redirect(url)
