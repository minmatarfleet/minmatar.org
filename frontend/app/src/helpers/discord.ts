import type { DiscordUser } from '@dtypes/discord'

const API_ENDPOINT = import.meta.env.API_ENDPOINT
const CLIENT_ID = import.meta.env.CLIENT_ID
const CLIENT_SECRET = import.meta.env.CLIENT_SECRET
const REDIRECT_URI = import.meta.env.REDIRECT_URI
const GUILD_ID = import.meta.env.GUILD_ID
const BOT_TOKEN = import.meta.env.BOT_TOKEN

export async function request_access_token(code:string) {
    const data = new URLSearchParams({
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI
    });

    const headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': `Basic ${btoa(`${CLIENT_ID}:${CLIENT_SECRET}`)}`
    }

    try {
        const response = await fetch(`${API_ENDPOINT}/oauth2/token`, {
            method: 'POST',
            body: data,
            headers: headers
        });

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        const json = await response.json();
        return json;
    } catch (error) {
        console.error('Error during token exchange:', error.message);
        throw error;
    }
}

export async function get_discord_user(token_type:string, access_token:string) {
    const response = await fetch(`${API_ENDPOINT}/users/@me`, {
        headers: {
            authorization: `Bearer ${access_token}`,
        },
    })

    return await response.json() as DiscordUser
}

export async function get_discord_member(access_token:string, user_id:string) {
    const headers = {
        'Authorization': `Bot ${BOT_TOKEN}`
    }

    const url = `${API_ENDPOINT}/guilds/${GUILD_ID}/members/${user_id}`;

    try {
        const response = await fetch(url, {
            headers: headers
        });

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        const json = await response.json();
        return json;
    } catch (error) {
        console.error('Error during guild member exchange:', error.message);
        throw error;
    }
}