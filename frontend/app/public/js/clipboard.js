function copyFitToClipboard(element_id, alert_text, source) {
    var copyText = document.getElementById(element_id);

    copyText.select();
    copyText.setSelectionRange(0, 99999);

    navigator.clipboard.writeText(copyText.value);

    if (source && window.capture_event) window.capture_event('fitting_copied', { source: source });

    if (alert_text) alert(alert_text + copyText.value);
}
