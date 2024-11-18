Overview
========
Eve combat log analyzer framework, for extracting useful information from the combat logs automatically recorded by the Eve Online client.

Usage
=====
In the Eve client, select `Utilities` on the NeoCom, then `Logs and Messages`. Use the "more" menu (three vertical dots) in the top right and "Copy Log to Clipboard".

Paste from the clipboard into the request body for the `/api/combatlog/` endpoint.

Alternatively, select an existing file from `$HOME\Documents\EVE\logs\Gamelogs`.

TO-DO
=====
* Capture character name from "Listener:" line
* Filter events by time range
* Capture system name changes and add to events
* Store high level stats (eg total damage) in database
* Capture max DPS dealt and received (10s period)
* Query by fleet ID, restricted to fleet commander
* Query by doctrine ID, restricted to Doctrines team

Done
----
* Initial API implementation
* Initial Frontend implementation
* Save to database if linked to doctrine or fleet
* API to retrieve saved combat log
* Combat log query API
