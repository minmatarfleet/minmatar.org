# Learning Center mentors

One-to-one classes on Discord. A pilot picks a mentor who plays when they do, asks for a class, and the mentor books a time. Both get a Discord DM with the time and the other's Discord name, and they talk in direct messages. Leadership sees how it went; the other person never does.

The Learning Center is split into tabs, each its own URL: Certificates (`/learning/`), Mentors (`/learning/mentors/`), Guides (`/learning/guides/`) and Skill plans (`/learning/skillplans/`).

## Who sees what

| Page | Path | Who |
| --- | --- | --- |
| Find a mentor | `/learning/mentors/` | Pilots with the `learning.mentors` feature (Alliance) |
| My mentees | `/learning/mentors/mentees/` | Mentors |
| My settings | `/learning/mentors/settings/` | Mentors, and pilots who asked to mentor |
| Settings | `/learning/mentors/admin/` | `learning.manage` |
| Metrics | `/learning/mentors/metrics/` | `learning.manage` |
| A class | `/learning/mentors/classes/<slug>/` | Everyone who can request |
| Class editor | `/learning/mentors/classes/new/`, `/learning/mentors/classes/<id>/edit/` | `learning.manage` (from Settings) |

There is no general intake: a pilot always asks one mentor.

## Matching

Mentors and pilots each have weekday brackets, weekend brackets and evening days (`backend/learning/mentors/availability.py`). The brackets are the timezone ones (`USTZ`, `USTZ+`, `EUTZ`, ...) from `backend/timezones/brackets.py`, on each region's own clock. An evening counts for the day it started, so a US evening that runs past midnight EVE is still that weekday.

A pilot's times start from their `PilotTimezone` (both weekday and weekend get the same brackets, because the record has no weekday/weekend split). They can change them on the request. A mentor sees their own card too, marked You, with a link to My settings instead of Request a class. Mentor cards are sorted by how well the times fit (`evenings`, `weekdays`, `weekends`, `none`), then by whether the mentor is full this week, then by classes taught.

Each card shows the mentor's weekday and weekend brackets as `TimezoneTags` (hover for the bracket's EVE hours today), a Monday–Sunday strip of the evenings they teach, how fast they answer ("Within a day" until they have answered someone), and their classes as cover tiles. A History row counts distinct pilots who finished a class with them (`pilots_mentored`). Past four classes the fourth tile becomes "+N more" and opens the rest. The Request button fills the card's footer. The card does not show how many requests a mentor has waiting. Cards sit at most three to a row.

## Life of a request

`MentorRequest.status` in `backend/learning/models.py`:

1. **asked**: the mentor gets a DM with Accept (a link to My mentees) and Pass (a bot button).
2. **passed** / **expired**: if the mentor passes, or doesn't answer in 2 days, the request moves to the next mentor who teaches the class and shares the most hours with the pilot. The new request keeps `passed_from`. When nobody fits, it expires and the pilot gets a DM.
3. **booked**: the mentor picks a suggested slot (the first hour of each shared evening in the next two weeks) or types a time. Both get a DM with the time, the other's `@handle` and a Message link.
4. **24 hours before**: both get a reminder with "I'll be there" and "Cancel the class".
5. **48 hours after**: the pilot is asked how it went (Really helped / Helped a bit / Didn't help / It didn't happen) and the mentor is asked whether it happened (Yes, done / Yes, needs another class / No-show / We moved it). Both answers go to learning managers under Class reports. "We moved it" puts the request back to asked.
6. **done** / **no_show** / **unconfirmed**: a mentor's done marks the class's Learning complete for the pilot. With no mentor answer 7 days after the follow-up, the class closes as unconfirmed.

Either side can cancel an asked or booked class. A pilot has at most one open request per class.

The schedule runs every 15 minutes in `learning.tasks.run_mentor_schedule` on the `community` queue.

## Classes

Learning managers set up classes in Settings (`Create a class`): title, description, outline, length, where (voice, screen share, in space), requirements and a background. A new class is a draft; the editor's Published switch publishes or hides it. Pilots only see published classes. The manager invites mentors to teach it (`MentorClassTeacher`); an invited mentor can accept before the class is published, and any mentor can join a published class from My settings. Mentors don't write or edit classes. Classes left waiting for review from before this change show under Settings and publish like a draft.

The background (`MentorClass.cover_image_url`) is picked from the site cover gallery that campaigns use (`backend/app/covers.py`), as thumbnails in the editor and in the Django admin. It is the class page's background; empty uses the Learning Center cover. `GET /admin/class-options` gives the editor the gallery and the requirement kinds.

Requirements (`backend/learning/mentors/requirements.py`) are checked against what the site already knows: days in the alliance, a class done, accounts linked, a doctrine fit ready, a certificate, a tribe group, a corporation. A pilot who misses one sees what to do and can't request yet.

Publishing creates a Learning row (`content_kind = mentor_class`, slug `mentor-<slug>`) that links to the class page, so a certificate can include a mentor class. The guides editor refuses to edit or create these rows; the class owns them.

## Discord

DMs go through the outbox (`discord.outbox.queue_dm`), sent after the transaction commits. Bot buttons use the custom ids in `bot/app/custom_ids.py` (`mentor:pass:`, `mentor:cancel:`, `mentor:confirm:`, `mentor_rate:*`, `mentor_close:*`), checked against the backend by `backend/discord/test_bot_custom_ids.py`. The bot calls the `discord-*` endpoints as the service account with the presser's Discord id. No channel or thread is created.

## Metrics

`backend/learning/mentors/metrics.py` computes on request (mentoring data is small): requests and pilots, the share that got a mentor (and from the first one asked), median hours to booked, classes done, a row per mentor, open requests by timezone against the mentors who cover it, and requests per class. The impact block compares mentored pilots with pilots who joined the same month and weren't mentored (fleets in the 30 days after the class, still flying at 90 days) and stays hidden until 10 mentored pilots are old enough.

## Code

- Backend: `backend/learning/mentors/` (service, availability, requirements, views, schemas, metrics, discord payloads) and one file per endpoint in `backend/learning/endpoints/mentors/`, mounted at `/api/learning/mentors`.
- Bot: `bot/app/mentors/`.
- Website: `frontend/app/src/pages/learning/mentors/`, the `mentor*` partials in `frontend/app/src/pages/partials/`, components in `frontend/app/src/components/blocks/mentors/`, and every POST action in `frontend/app/src/helpers/mentors_actions.ts`.
- Tests: `backend/learning/tests/test_mentors.py`.
