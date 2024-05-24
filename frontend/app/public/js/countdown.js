const countdown = (element, id, date, expired_text) => {
    // Set the date we're counting down to
    const countDownDate = new Date(date).getTime()
    
    // Update the count down every 1 second
    var x = setInterval(function() {
        // Get today's date and time
        const now = new Date().getTime()
        
        // Find the distance between now and the count down date
        const distance = countDownDate - now

        // Time calculations for days, hours, minutes and seconds
        let days = distance / (1000 * 60 * 60 * 24)
        days = (days > 0 ? Math.floor(days) : Math.ceil(days))
        let hours = (distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60)
        hours = (hours > 0 ? Math.floor(hours) : Math.ceil(hours))
        let minutes = (distance % (1000 * 60 * 60)) / (1000 * 60)
        minutes = (minutes > 0 ? Math.floor(minutes) : Math.ceil(minutes))
        let seconds = (distance % (1000 * 60)) / 1000
        seconds = (seconds > 0 ? Math.floor(seconds) : Math.ceil(seconds))
        
        if (document.querySelector(element)) {
            document.querySelector(element).innerHTML = distance < 0 && expired_text ?
                expired_text :
                pad(Math.abs(days * 24 +  hours)) + " : " + pad(Math.abs(minutes)) + " : " + pad(Math.abs(seconds))
            
            if (distance < 0)
                document.querySelector(element).classList.add('expired');

            if (distance < 0 && expired_text) {
                document.querySelector(element).classList.add('expired-text');
                
                const event = new CustomEvent('countdown', {
                    detail: {
                        id: id
                    }
                });
                
                window.dispatchEvent(event);

                clearInterval(x);
            }
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