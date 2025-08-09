# Discord Setup For Local Development with Discord Integration

This guide walks you through setting up Discord integration for the minmatar.org platform, including creating a Discord server, application, and bot for the purposes of local development

## Overview

The minmatar.org platform integrates with Discord for:
- **User Authentication**: Single sign-on using Discord OAuth2
- **Role Management**: Automatic role synchronization between the application and Discord server
- **Notifications**: Fleet pings, structure alerts, and administrative messages
- **Bot Commands**: Timer submissions
- **User Management**: Nickname synchronization and automatic role assignment

## Step 1: Create Discord Accounts

**Note**: It is recommended to use at least two discord accounts, one to setup the server/discord app/discord bot, and one to act as a user.
If needed you can go further and have a third so that you can have one user be a 'director' and one be a 'regular joe' for testing such things as team applications or corp applications as well as permissions.

To use multiple discord accounts at the same time on the same device you can utilize private/incognito browsing,  or you can use different browsers (like firefox + chrome + edge).

you can use your existing main discord account as one of these. It is recomended to use your main discord account as the admin, so the others are disposable and you won't lose the server/app/bot setup.

## Step 2: Create Discord Application

Do this while logged in as the discord user you wish to act as 'admin' (likely your main)

1. **Go to Discord Developer Portal**:
   - Visit: https://discord.com/developers/applications
   - Click "New Application"
   - Give it a name (e.g., "Minmatar Fleet App - Dev")

2. **Configure OAuth2 Settings**:
   - Go to "OAuth2"
   - Add Redirect URLs:
     - `http://localhost:8000/api/users/callback` (for development)
     - `http://localhost:8000/oauth2/login/redirect` (for admin login)

3. **Get Application Credentials**:
   - From "OAuth2":
     - Copy **Client ID** → `DISCORD_CLIENT_ID`
     - Click Reset Secret. Then Copy **Client Secret** → `DISCORD_CLIENT_SECRET`
     - ⚠️ **Keep this token secret!**


## Step 2: Create Discord Server

Do this while logged in as the discord user you wish to act as 'admin' (likely your main)

1. **Use the provided template** to create your Discord server:
   - Click this link: https://discord.new/eJBCDrW8kWgA (or check with technology team if it has gone stale)
   - This creates a server with the appropriate channel and role structure for minmatar.org

2. **Get your Server ID** (Guild ID):
   - Right-click on your server name → "Copy Server ID"
   - Save this ID - you'll need it for `DISCORD_GUILD_ID`

## Step 3: Create Discord Bot

1. **Enable Bot in your Application**:
   - Go to "Bot" section in your Discord application
   - Click "Add Bot" if not already created
   - Configure bot settings:
     - Set a username (e.g., "Minmatar Fleet")
     - Upload an avatar if desired

2. **Configure Bot Settings**:
   - In the "Bot" section, enable these.
     - **Authorization Flow**:
       - Public Bot: True
       - Requires OAuth2 Code Grant: False
     - **Privileged Gateway Intents**:       
       - Presence Intent: False
       - Server Members Intent: True
       - Message Content Intent: True
   
3. **Get Bot Token**:
   - In "Bot" section, click "Reset Token"
   - Copy the token → `DISCORD_BOT_TOKEN`
   - ⚠️ **Keep this token secret!**

## Step 4: Invite Bot to Server

1. **Generate Invite Link**:
   - Go to "OAuth2" → "URL Generator"
   - Select scopes:
     - ✅ `bot`
     - ✅ `applications.commands`
   - Select bot permissions
     - ✅ `View Channels`
     - ✅ `Send Messages`
     - ✅ `Manage Roles`
     - ✅ `Manage Nicknames`
     - ✅ `Create Public Threads`
     - ✅ `Send Messages in Threads`
     - ✅ `Use Slash Commands`
     - The permission bitmask is 311787785216 FYI
   - Copy the URL

2. **Invite Bot**:
   - Open the generated URL in your browser while logged in as the dev server admin
   - Select your server
   - Authorize the bot

## Step 5: Configure Bot Role Hierarchy

1. **Set Bot Role Position**:
   - Go to your Discord server
   - Right-click the server name → "Server Settings"
   - Go to "Roles" in the left sidebar
   - Find the role matching your bot's name (auto-created when bot joined)
   - Drag this role to the **top** of the role list
   - ⚠️ **Important**: The bot can only manage roles positioned **below** its own role in the hierarchy

## Step 6: Configure Environment Variables

Set these variables to your `.env` file:

```bash
# Discord Integration
DISCORD_BOT_TOKEN=your_bot_token_here
DISCORD_CLIENT_ID=your_client_id_here
DISCORD_CLIENT_SECRET=your_client_secret_here
...

# Server and Channel Configuration
DISCORD_GUILD_ID=your_server_id_here
DISCORD_PEOPLE_TEAM_CHANNEL_ID=your_people_channel_id_here
DISCORD_TECHNOLOGY_TEAM_CHANNEL_ID=your_tech_channel_id_here
... others
```

## Step 7: Some Manual Steps For Permissions

These could be automated at some point

### Schedule Channel
1. Go to the `Schedule` Channel in your discord server. 
1. In the main chat pane click `Add members or roles`
1. Select the role matching the name of your bot to add it to the channel
1. In the channel select click `edit settings` on the `Schedule` channel
1. Under Permissions -> Advanced Permissions click your bot role name
1. Tick the `View Channel` permission
1. Tick the `Send Messages` permission

### Other Private Channels

For any other private channels that the bot may interact with follow these steps.
(e.g. people team, tech team and alliance-pings all receive messages from the bot)

1. In the main chat pane click `Add members or roles`
1. Select the role matching the name of your bot to add it to the channel

## Step 8: Bot App Setup (local Bot Application)

this application constantly listens to the discord server for live interaction.
currently features are /timer to post a time.


1. **Configure Bot Environment**:
   - Create .env from .env.example in the bot folder (`bot/.env`):
   ```bash
   DISCORD_BOT_TOKEN=your_bot_token_here
   MINMATAR_API_TOKEN=your_api_token_here
   DISCORD_GUILD_ID=your_guild_id
   ... plus any channel ids needed
   ```

## Step 9: Verify the setup

```bash
# Check Discord API connectivity
cd backend
source .env
python manage.py shell_plus
from discord.client import DiscordClient
discord = DiscordClient()
discord.get_roles()  # Should return server roles
```

## Step 10: send a test message (and get Schedule channel set up)

Right Click the Schedule Channel, Copy Channel ID for this script
```bash
# Send a Message
cd backend
source .env
python manage.py shell_plus
from discord.client import DiscordClient
discord = DiscordClient()
discord.create_message(123456789, 'primer message')  # use the channel id instead of 123456789
```
Now right click the timestamp of the message in discord, `copy message id` and use this message id in `backend/.env` for the `DISCORD_FLEET_SCHEDULE_MESSAGE_ID` which gets updated by discord api when fleet schedules change

## Security Considerations

- **Never commit tokens or secrets** to version control
- Use environment variables for all secrets

For Discord API documentation: https://discord.com/developers/docs
