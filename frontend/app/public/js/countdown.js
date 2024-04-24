const countdown = (element, date, expired_text) => {
    // Set the date we're counting down to
    var countDownDate = new Date(date).getTime();

    // Update the count down every 1 second
    var x = setInterval(function() {
        // Get today's date and time
        var now = new Date().getTime();
            
        // Find the distance between now and the count down date
        var distance = countDownDate - now;
            
        // Time calculations for days, hours, minutes and seconds
        var days = distance / (1000 * 60 * 60 * 24);
        days = (days > 0 ? Math.floor(days) : Math.ceil(days));
        var hours = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
        var minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
        var seconds = Math.floor((distance % (1000 * 60)) / 1000);
        
        if (document.querySelector(element)) {
            document.querySelector(element).innerHTML = distance < 0 && expired_text ?
                expired_text :
                pad(Math.abs(days * 24 +  hours)) + " : " + pad(Math.abs(minutes)) + " : " + pad(Math.abs(seconds))
            
            if (distance < 0)
                document.querySelector(element).classList.add('expired');

            if (distance < 0 && expired_text)
                document.querySelector(element).classList.add('expired-text');
        } else {
            clearInterval(x);
        }
    }, 1000);
}

const pad = (num) => {
    if (num < 10)
        return `0${num}`;
    
    return num;
}