/**
 * Searchable Select2 for the EveFitting known_key ChoiceField.
 * Uses Django admin's bundled Select2 (no AJAX).
 */
(function ($) {
  function initKnownKeySelect(element) {
    var $element = $(element);
    if ($element.hasClass("select2-hidden-accessible")) {
      return;
    }
    $element.select2({
      width: "100%",
      theme: element.getAttribute("data-theme") || "admin-autocomplete",
      allowClear: element.getAttribute("data-allow-clear") !== "false",
      placeholder:
        element.getAttribute("data-placeholder") || "Search known keys…",
      dropdownAutoWidth: true,
    });
  }

  $(function () {
    document
      .querySelectorAll("select.known-key-select")
      .forEach(initKnownKeySelect);
  });
})(django.jQuery);
