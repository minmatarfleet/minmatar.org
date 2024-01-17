function copyFitToClipboard(element_id, alert_text) {
    var copyText = document.getElementById(element_id);

    copyText.select();
    copyText.setSelectionRange(0, 99999);

    navigator.clipboard.writeText(copyText.value);

    if (alert_text) alert(alert_text + copyText.value);
}