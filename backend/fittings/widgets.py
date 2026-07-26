"""Admin widgets for fittings."""

from django import forms


class SearchableKnownFittingSelect(forms.Select):
    """Select2-backed known_key picker (type-to-filter, clearable)."""

    def __init__(self, attrs=None, choices=()):
        default_attrs = {
            "class": "admin-autocomplete known-key-select",
            "data-theme": "admin-autocomplete",
            "data-allow-clear": "true",
            "data-placeholder": "Search known keys…",
        }
        if attrs:
            merged = {**default_attrs, **attrs}
            if "class" in attrs and "known-key-select" not in attrs["class"]:
                merged["class"] = f"{attrs['class']} known-key-select"
            default_attrs = merged
        super().__init__(attrs=default_attrs, choices=choices)

    class Media:
        css = {
            "screen": (
                "admin/css/vendor/select2/select2.css",
                "admin/css/autocomplete.css",
            )
        }
        js = (
            "admin/js/vendor/jquery/jquery.js",
            "admin/js/vendor/select2/select2.full.js",
            "admin/js/jquery.init.js",
            "fittings/admin/known_key_select.js",
        )
