self.addEventListener('activate', async (e) => {
    await subscribe()
})

async function subscribe() {
    const url = new URL(location)
    const endpoint = url.searchParams.get('endpoint')
    const public_key = url.searchParams.get('public_key')

    const subscription = await self.registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(public_key)
    })

    await save_subscription(endpoint, subscription)
}

self.addEventListener('push', function(event) {
    const data = event.data.json();
    const options = {
        body: data.body,
        icon: data.icon,
        data: { url: data.url },
        requireInteraction: true,
    }

    event.waitUntil(
        self.registration.showNotification(data.title, options)
    )
})

self.addEventListener('notificationclick', function(event) {
    event.notification.close()
    event.waitUntil(
        clients.openWindow(event.notification.data.url)
    )
});

const MINUTE = 60*1000
setInterval(check_and_subscribe, MINUTE)

async function check_and_subscribe() {
    self.registration.pushManager
        .getSubscription()
        .then((subscription) => {
            if (!subscription)
                subscribe().then()
        })
        .catch((err) => {
            console.error(`Error during getSubscription(): ${err}`);
        });
}

const save_subscription = async (endpoint, subscription) => {
    await fetch(endpoint, {
        method: 'post',
        headers: { 'Content-type': 'application/json' },
        body: JSON.stringify(subscription)
    })
}

const urlBase64ToUint8Array = base64String => {
    const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding)
        .replace(/\-/g, '+')
        .replace(/_/g, '/');

    const rawData = atob(base64);
    const outputArray = new Uint8Array(rawData.length);

    for (let i = 0; i < rawData.length; ++i) {
        outputArray[i] = rawData.charCodeAt(i);
    }

    return outputArray;
}