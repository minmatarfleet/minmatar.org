/**
 * Extend Django admin-autocomplete AJAX with fitting_id / preferred_id.
 * Do not destroy/recreate Select2 — that drops data-ajax--url and breaks fetches.
 */
(function ($) {
  function preferredSelect(element) {
    var row = element.closest("tr");
    if (!row) {
      return null;
    }
    return row.querySelector('select[name*="-preferred_module"]');
  }

  function patchAjaxData(element, originalData) {
    return function (params) {
      var data =
        typeof originalData === "function"
          ? originalData(params)
          : {
              term: params.term,
              page: params.page,
              app_label: element.dataset.appLabel,
              model_name: element.dataset.modelName,
              field_name: element.dataset.fieldName,
            };
      if (element.dataset.fittingId) {
        data.fitting_id = element.dataset.fittingId;
      }
      if (element.dataset.fieldName === "substitute_module") {
        var preferred = preferredSelect(element);
        if (preferred && preferred.value) {
          data.preferred_id = preferred.value;
        }
      }
      return data;
    };
  }

  var original = $.fn.djangoAdminSelect2;
  if (!original) {
    return;
  }

  $.fn.djangoAdminSelect2 = function () {
    $.each(this, function (_i, element) {
      var $element = $(element);
      if (!element.dataset.fittingId) {
        original.call($element);
        return;
      }
      $element.select2({
        ajax: {
          url: element.getAttribute("data-ajax--url"),
          dataType: "json",
          delay: 250,
          data: patchAjaxData(element),
          processResults: function (data, params) {
            params.page = params.page || 1;
            return {
              results: data.results,
              pagination: {
                more: Boolean(data.pagination && data.pagination.more),
              },
            };
          },
        },
        theme: element.getAttribute("data-theme") || "admin-autocomplete",
        allowClear: element.getAttribute("data-allow-clear") === "true",
        placeholder: element.getAttribute("data-placeholder") || "",
      });
    });
    return this;
  };
})(django.jQuery);
