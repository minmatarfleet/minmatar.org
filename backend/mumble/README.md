# Access to Mumble/Murmur server

## Overview
The `backend/mumble` package creates a user with a temporary password in the database and provides an API endpoint to launch the Mumble client using those credentials.

The `backend/mumble.py` file is then built into a container that uses the ICE API to install a custom `Authenticator` that reads user details from this database.

## Implementation
The Mumble user details are stored in the `MumbleAccessManager` model, linked to a Django `User`. The Mumble username is set to the primary character's name.

There is also a "suspended" flag which can be used to block the user from logging in to Mumble.