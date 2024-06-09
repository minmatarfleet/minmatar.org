export const countdown = (date, expired_text = '') => {
    // Set the date we're counting down to
    var countDownDate = new Date(date).getTime();

    // Get today's date and time
    var now = new Date().getTime();
        
    // Find the distance between now and the count down date
    var distance = countDownDate - now;
        
    // Time calculations for days, hours, minutes and seconds
    let days = distance / (1000 * 60 * 60 * 24)
    days = (days > 0 ? Math.floor(days) : Math.ceil(days))
    let hours = (distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60)
    hours = (hours > 0 ? Math.floor(hours) : Math.ceil(hours))
    let minutes = (distance % (1000 * 60 * 60)) / (1000 * 60)
    minutes = (minutes > 0 ? Math.floor(minutes) : Math.ceil(minutes))
    let seconds = (distance % (1000 * 60)) / 1000
    seconds = (seconds > 0 ? Math.floor(seconds) : Math.ceil(seconds))
    
    return {
        expired: (distance < 0),
        text: pad(Math.abs(days * 24 +  hours)) + " : " + pad(Math.abs(minutes)) + " : " + pad(Math.abs(seconds))
    }
}

const pad = (num) => {
    if (num < 10)
        return `0${num}`;
    
    return num;
}