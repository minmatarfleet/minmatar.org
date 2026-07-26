(function() {
  function init() {
    var sovSelect = document.getElementById('id_sov_system');
    var anomalySelect = document.getElementById('id_site_name');
    if (!sovSelect || !anomalySelect) return;

    function clearAnomaly() {
      anomalySelect.innerHTML = '<option value="">---------</option>';
    }

    function loadAnomalies(pk) {
      if (!pk) {
        clearAnomaly();
        return;
      }
      var path = window.location.pathname;
      var base = path.replace(/\/(?:add|\d+\/change)(?:\/.*)?$/, '');
      var url = base + '/anomalies/?sov_system_id=' + encodeURIComponent(pk);
      fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
        .then(function(r) { return r.json(); })
        .then(function(data) {
          anomalySelect.innerHTML = '<option value="">---------</option>';
          data.forEach(function(a) {
            var opt = document.createElement('option');
            opt.value = a.name;
            opt.textContent = a.qty ? a.name + ' (×' + a.qty + ')' : a.name;
            anomalySelect.appendChild(opt);
          });
        })
        .catch(function() { clearAnomaly(); });
    }

    sovSelect.addEventListener('change', function() {
      loadAnomalies(this.value);
    });
    if (sovSelect.value) {
      loadAnomalies(sovSelect.value);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
