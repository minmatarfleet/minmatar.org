"""Restore corporation applications removed on 2026-09-24.

Nickname sync deleted a recruiter, and processed_by CASCADE removed every
application that account had accepted or rejected. These rows are rebuilt
from the Discord starter posts. Existing threads stay locked.

Keldor Eternia's Rattini application (id 1346) is omitted: that applicant
account was deleted in the same offboard, so there is no user to attach.
"""

import json

from django.db import migrations
from django.utils.dateparse import parse_datetime

SNAPSHOT = r"""[
  {
    "id": 1958,
    "user_id": 3094,
    "corporation_id": 98838663,
    "description": "Mining with MRECK. Ive been around 6 months, I like to dip in and out of FW, basically getting a big purse, building a ton of ships, and then yeeting those ships into plexes and Amarr scum! I like mining and building, I hate buying everything all the time.\n\nQuestionnaire:\n- Timezone: America/Toronto (EDT) — US region, afternoons → EUTZ - USTZ\n- Roles interested in: Fleet damage (guns, missiles, etc), Fleet logistics (healing), Fleet support (painting, tackling, etc), Small gang combat (<10 pilots), Resource harvesting (mining, planet harvesting, etc), Production (building things)\n- Doctrine ships: Typhoon and Raven cruise missile builds. When these aren't needed for fleet I start throwing slasher tackles out, or stiletto if there are meaningful stakes.\n\nAffiliation disclosure:\n- Alt of existing player: Yes (main character: Maurdakar)\n- Member of another alliance: No\n\nRequirements confirmed:\n- ✅ All characters added to website (including ones not joining)\n- ✅ Agree to alliance values",
    "status": "accepted",
    "discord_thread_id": 1533166091159867522,
    "created_at": "2026-08-01T17:34:40.981000+00:00",
    "updated_at": "2026-08-03T22:02:26.584000+00:00"
  },
  {
    "id": 1966,
    "user_id": 3784,
    "corporation_id": 98838663,
    "description": "Playstyle mostly. Saw the post on Reddit.\n\nQuestionnaire:\n- Timezone: America/Chicago (CDT) — US region, evenings → USTZ\n- Roles interested in: Resource harvesting (mining, planet harvesting, etc), Production (building things)\n- Doctrine ships: I have not played in a very long time, so I am having to get many new skills trained to fly things. I can fly T1 mining barges without the best equipment.\n\nAffiliation disclosure:\n- Alt of existing player: No\n- Member of another alliance: No\n\nRequirements confirmed:\n- ✅ All characters added to website (including ones not joining)\n- ✅ Agree to alliance values",
    "status": "accepted",
    "discord_thread_id": 1533556767429099551,
    "created_at": "2026-08-02T19:27:05.462000+00:00",
    "updated_at": "2026-08-03T22:01:34.490000+00:00"
  },
  {
    "id": 1994,
    "user_id": 3860,
    "corporation_id": 98838663,
    "description": "I flew in a fleet and you guys seem cool\n\nQuestionnaire:\n- Timezone: America/Los_Angeles (PDT) — US region, evenings → USTZ\n- Roles interested in: Resource harvesting (mining, planet harvesting, etc), Production (building things)\n- Doctrine ships: I probably can't fly these ships but I can train for them\n\nAffiliation disclosure:\n- Alt of existing player: Yes (main character: The Bungulator)\n- Member of another alliance: No\n\nRequirements confirmed:\n- ✅ All characters added to website (including ones not joining)\n- ✅ Agree to alliance values",
    "status": "accepted",
    "discord_thread_id": 1535764181259649054,
    "created_at": "2026-08-08T21:38:33.931000+00:00",
    "updated_at": "2026-08-11T01:49:09.655000+00:00"
  },
  {
    "id": 1997,
    "user_id": 3326,
    "corporation_id": 98838663,
    "description": "Has mining alt want to contribute to the boom\n\nQuestionnaire:\n- Timezone: America/Chicago (CDT) — US region, evenings → USTZ\n- Roles interested in: Resource harvesting (mining, planet harvesting, etc), Production (building things)\n- Doctrine ships: T2 miner/ Orca\n\nAffiliation disclosure:\n- Alt of existing player: Yes (main character: Psycho Ex)\n- Member of another alliance: No\n\nRequirements confirmed:\n- ✅ All characters added to website (including ones not joining)\n- ✅ Agree to alliance values",
    "status": "rejected",
    "discord_thread_id": 1535825247662505985,
    "created_at": "2026-08-09T01:41:13.296000+00:00",
    "updated_at": "2026-08-11T03:58:35.542000+00:00"
  },
  {
    "id": 2008,
    "user_id": 3892,
    "corporation_id": 98838663,
    "description": "A friend recommended you.\n\nQuestionnaire:\n- Timezone: America/Toronto (EDT) — US region, evenings → USTZ\n- Roles interested in: Resource harvesting (mining, planet harvesting, etc)\n- Doctrine ships: Pretty much anything under Omega. Though I rather use mining related ships\n\nAffiliation disclosure:\n- Alt of existing player: No\n- Member of another alliance: No\n\nRequirements confirmed:\n- ✅ All characters added to website (including ones not joining)\n- ✅ Agree to alliance values",
    "status": "accepted",
    "discord_thread_id": 1536920429329907768,
    "created_at": "2026-08-12T02:13:04.953000+00:00",
    "updated_at": "2026-08-14T08:47:10.267000+00:00"
  },
  {
    "id": 2017,
    "user_id": 3906,
    "corporation_id": 98838663,
    "description": "Your playstle, I just want to chill and build stuff in the future\n\nQuestionnaire:\n- Timezone: Asia/Manila (GMT+8) — Asia-Pacific region, mornings → EUTZ - USTZ\n- Roles interested in: Resource harvesting (mining, planet harvesting, etc), Production (building things)\n- Doctrine ships: Tackle Punisher\n\nAffiliation disclosure:\n- Alt of existing player: No\n- Member of another alliance: No\n\nRequirements confirmed:\n- ✅ All characters added to website (including ones not joining)\n- ✅ Agree to alliance values",
    "status": "accepted",
    "discord_thread_id": 1537814881087135865,
    "created_at": "2026-08-14T13:27:18.870000+00:00",
    "updated_at": "2026-08-14T15:03:09.368000+00:00"
  },
  {
    "id": 2019,
    "user_id": 3778,
    "corporation_id": 98838663,
    "description": "Mining in a group is more fun! And helping FL33T at the same time - fire! \nApplying my alt\n\nQuestionnaire:\n- Timezone: America/Edmonton (MDT) — US region, evenings → USTZ\n- Roles interested in: Resource harvesting (mining, planet harvesting, etc)\n- Doctrine ships: Retriever now - can learn into something else later\n\nAffiliation disclosure:\n- Alt of existing player: Yes (main character: Eresh Kidu)\n- Member of another alliance: No\n\nRequirements confirmed:\n- ✅ All characters added to website (including ones not joining)\n- ✅ Agree to alliance values",
    "status": "rejected",
    "discord_thread_id": 1537938283483365488,
    "created_at": "2026-08-14T21:37:40.294000+00:00",
    "updated_at": "2026-08-15T05:08:55.516000+00:00"
  },
  {
    "id": 2021,
    "user_id": 3914,
    "corporation_id": 98838663,
    "description": "I live and play in Minmatar space. I've heard a lot of good things about your alliance, and I share your values.\n\nQuestionnaire:\n- Timezone: Europe/Budapest (GMT+2) — Europe region, evenings → EUTZ\n- Roles interested in: Fleet logistics (healing), Fleet support (painting, tackling, etc), Small gang combat (<10 pilots), Resource harvesting (mining, planet harvesting, etc), Production (building things)\n- Doctrine ships: Exequror, Maller, Slasher, Vigil, Punisher\n\nAffiliation disclosure:\n- Alt of existing player: Yes (main character: Dervy)\n- Member of another alliance: Yes (Ivy League)\n\nRequirements confirmed:\n- ✅ All characters added to website (including ones not joining)\n- ✅ Agree to alliance values",
    "status": "accepted",
    "discord_thread_id": 1538304283932500018,
    "created_at": "2026-08-15T21:52:01.601000+00:00",
    "updated_at": "2026-08-16T10:28:52.373000+00:00"
  },
  {
    "id": 2023,
    "user_id": 3923,
    "corporation_id": 98838663,
    "description": "I'm a returning eve player, I used to do missioneering and a bit of scanning/data sites. I'm interested in getting into the industry side of things, but also learning a bit of PVP.\n\nI want to move back to minmitar space, and I've always liked the rust! I want to help push the rust industry o7\n\nQuestionnaire:\n- Timezone: Australia/Sydney (GMT+10) — Asia-Pacific region, evenings → AUTZ\n- Roles interested in: Solo combat, Small gang combat (<10 pilots), Resource harvesting (mining, planet harvesting, etc), Production (building things)\n- Doctrine ships: Wolf, Vigil, Slasher, Tackle Punisher, RHML Typhoon Fleet Issue, HML Drake Navy Issue, Osprey Navy Issue, Armor Scorpion, 10MN Exequror, 10MN Augoror, Tackle Maller\n\nAffiliation disclosure:\n- Alt of existing player: No\n- Member of another alliance: No\n\nRequirements confirmed:\n- ✅ All characters added to website (including ones not joining)\n- ✅ Agree to alliance values",
    "status": "accepted",
    "discord_thread_id": 1538437438400364565,
    "created_at": "2026-08-16T06:41:08.100000+00:00",
    "updated_at": "2026-08-19T06:12:37.458000+00:00"
  },
  {
    "id": 2026,
    "user_id": 3921,
    "corporation_id": 98838663,
    "description": "Im new to eve and really like mining and looking to get into small pvp, i noitced thats what yall are about and thought this might be the best first corp in eve\n\nQuestionnaire:\n- Timezone: America/Chicago (CDT) — US region, afternoons → EUTZ - USTZ\n- Roles interested in: Fleet damage (guns, missiles, etc), Fleet logistics (healing), Fleet support (painting, tackling, etc), Solo combat, Small gang combat (<10 pilots), Resource harvesting (mining, planet harvesting, etc), Production (building things)\n- Doctrine ships: None yet i dont think\n\nAffiliation disclosure:\n- Alt of existing player: No\n- Member of another alliance: No\n\nRequirements confirmed:\n- ✅ All characters added to website (including ones not joining)\n- ✅ Agree to alliance values",
    "status": "accepted",
    "discord_thread_id": 1538483582342008892,
    "created_at": "2026-08-16T09:44:29.673000+00:00",
    "updated_at": "2026-08-19T05:47:53.238000+00:00"
  },
  {
    "id": 2027,
    "user_id": 3926,
    "corporation_id": 98838663,
    "description": "I am a newer player to the game. been wanting to join a corporation for a little while. I took a liking to mining and want to learn more about it.\n\nQuestionnaire:\n- Timezone: America/Chicago (CDT) — US region, afternoons → EUTZ - USTZ\n- Roles interested in: Fleet damage (guns, missiles, etc), Resource harvesting (mining, planet harvesting, etc)\n- Doctrine ships: I dont know if i cany fly any ships yet\n\nAffiliation disclosure:\n- Alt of existing player: No\n- Member of another alliance: No\n\nRequirements confirmed:\n- ✅ All characters added to website (including ones not joining)\n- ✅ Agree to alliance values",
    "status": "accepted",
    "discord_thread_id": 1538485956779446372,
    "created_at": "2026-08-16T09:53:55.783000+00:00",
    "updated_at": "2026-08-19T05:48:05.843000+00:00"
  },
  {
    "id": 2034,
    "user_id": 3937,
    "corporation_id": 98838663,
    "description": "I am highly interest in mining with a corps\n\nQuestionnaire:\n- Timezone: Europe/Berlin (GMT+2) — Europe region, evenings → EUTZ\n- Roles interested in: Resource harvesting (mining, planet harvesting, etc), Production (building things)\n- Doctrine ships: Mackinaw, orca, retriever(if not in high sec)\n\nAffiliation disclosure:\n- Alt of existing player: No\n- Member of another alliance: No\n\nRequirements confirmed:\n- ✅ All characters added to website (including ones not joining)\n- ✅ Agree to alliance values",
    "status": "accepted",
    "discord_thread_id": 1538846012934987866,
    "created_at": "2026-08-17T09:44:39.860000+00:00",
    "updated_at": "2026-08-17T14:49:09.863000+00:00"
  },
  {
    "id": 2036,
    "user_id": 3936,
    "corporation_id": 98838663,
    "description": "I met some great people in the asteroid belts who share similar interests and encouraged me to join the cause for the greater good.\n\nQuestionnaire:\n- Timezone: Europe/Budapest (GMT+2) — Europe region, afternoons → AUTZ - EUTZ\n- Roles interested in: Resource harvesting (mining, planet harvesting, etc), Production (building things)\n- Doctrine ships: My main interest is on mining and industry, currently running alpha while learning the game. So Venture, pioneer.\n\nAffiliation disclosure:\n- Alt of existing player: No\n- Member of another alliance: No\n\nRequirements confirmed:\n- ✅ All characters added to website (including ones not joining)\n- ✅ Agree to alliance values",
    "status": "accepted",
    "discord_thread_id": 1538857073801044019,
    "created_at": "2026-08-17T10:28:36.976000+00:00",
    "updated_at": "2026-08-17T10:32:42.533000+00:00"
  },
  {
    "id": 2044,
    "user_id": 3956,
    "corporation_id": 98838663,
    "description": "This input filed doesn't allow me to type it all:D I've made a reddit post here: https://www.reddit.com/r/evejobs/comments/1vsuq9u/looking_for_a_corp_in_which_i_can_play_this_as_an/\nAnd got linked to you guys. From what I can see, you guys seem to love this game. I just want to shoot lasers at rocks\n\nQuestionnaire:\n- Timezone: Europe/Belgrade (GMT+2) — Europe region, afternoons → AUTZ - EUTZ\n- Roles interested in: Resource harvesting (mining, planet harvesting, etc)\n- Doctrine ships: None of those I think?I'm an alpha currently, with the goal of going omega purely from mining if that's possible. Was omega before, flew a retriever, currently just flying a venture. Active times below doesn't allow me to select multiple,noon to midn\n\nAffiliation disclosure:\n- Alt of existing player: No\n- Member of another alliance: Yes (To be honest I have no idea which allian)\n\nRequirements confirmed:\n- ✅ All characters added to website (including ones not joining)\n- ✅ Agree to alliance values",
    "status": "accepted",
    "discord_thread_id": 1539729825202180166,
    "created_at": "2026-08-19T20:16:37.125000+00:00",
    "updated_at": "2026-08-19T21:48:45.464000+00:00"
  },
  {
    "id": 2047,
    "user_id": 3963,
    "corporation_id": 98838663,
    "description": "Saw your content on reddit and youtube. Drawn by your story about your community and values!\n\nQuestionnaire:\n- Timezone: America/New_York (EDT) — US region, evenings → USTZ\n- Roles interested in: Resource harvesting (mining, planet harvesting, etc), Production (building things)\n- Doctrine ships: On my main i have about 44M SP and can fly various ships. For mining purposes on my main i can fly Exhumers.  On 2 of my alts i can also fly Exhumers and the 3rd alt i am highly skilled into providing some serious mining boosts in a Porpoise\n\nAffiliation disclosure:\n- Alt of existing player: No\n- Member of another alliance: No\n\nRequirements confirmed:\n- ✅ All characters added to website (including ones not joining)\n- ✅ Agree to alliance values",
    "status": "accepted",
    "discord_thread_id": 1540203162601005168,
    "created_at": "2026-08-21T03:37:29.555000+00:00",
    "updated_at": "2026-08-21T16:09:34.471000+00:00"
  },
  {
    "id": 2049,
    "user_id": 115,
    "corporation_id": 98838663,
    "description": "Moving from Rattini Tribe to M-EXC\n\nQuestionnaire:\n- Timezone: Australia/Sydney (GMT+10) — Asia-Pacific region, evenings → AUTZ\n- Roles interested in: Resource harvesting (mining, planet harvesting, etc), Production (building things)\n- Doctrine ships: All\n\nAffiliation disclosure:\n- Alt of existing player: No\n- Member of another alliance: No\n\nRequirements confirmed:\n- ✅ All characters added to website (including ones not joining)\n- ✅ Agree to alliance values",
    "status": "rejected",
    "discord_thread_id": 1540319020182540289,
    "created_at": "2026-08-21T11:17:52.155000+00:00",
    "updated_at": "2026-08-21T14:25:18.434000+00:00"
  },
  {
    "id": 2052,
    "user_id": 3960,
    "corporation_id": 98838663,
    "description": "all of the above\n\nQuestionnaire:\n- Timezone: Europe/Berlin (GMT+2) — Europe region, evenings → EUTZ\n- Roles interested in: Resource harvesting (mining, planet harvesting, etc)\n- Doctrine ships: none\n\nAffiliation disclosure:\n- Alt of existing player: No\n- Member of another alliance: No\n\nRequirements confirmed:\n- ✅ All characters added to website (including ones not joining)\n- ✅ Agree to alliance values",
    "status": "accepted",
    "discord_thread_id": 1540411583539314720,
    "created_at": "2026-08-21T17:25:40.979000+00:00",
    "updated_at": "2026-08-25T21:59:27.676000+00:00"
  },
  {
    "id": 2058,
    "user_id": 3954,
    "corporation_id": 98838663,
    "description": "I joined the Minmatar Fleet Academy with my main Festur Beilius and would like to get my miner alt here so I can help us better to keep fighting the Amarr zealots.\n\nQuestionnaire:\n- Timezone: Europe/Helsinki (GMT+3) — Europe region, early mornings → USTZ\n- Roles interested in: Resource harvesting (mining, planet harvesting, etc)\n- Doctrine ships: I can fly a barge.\n\nAffiliation disclosure:\n- Alt of existing player: Yes (main character: Festur Beilius)\n- Member of another alliance: No\n\nRequirements confirmed:\n- ✅ All characters added to website (including ones not joining)\n- ✅ Agree to alliance values",
    "status": "rejected",
    "discord_thread_id": 1540983079324090398,
    "created_at": "2026-08-23T07:16:36.192000+00:00",
    "updated_at": "2026-08-25T22:02:40.065000+00:00"
  },
  {
    "id": 2067,
    "user_id": 3971,
    "corporation_id": 98838663,
    "description": "lThe truth is, I was mining as usual when they invited me to join their fleet. Very kind of them, actually. And for such a hostile environment, it was a great surprise, especially since sometimes I play alone in a corps that's a bit inactive and it was getting boring. Thanks and regards.\n\nQuestionnaire:\n- Timezone: America/La_Paz (GMT-4) — US region, evenings → USTZ\n- Roles interested in: Resource harvesting (mining, planet harvesting, etc)\n- Doctrine ships: I've only used the Thrasher and Vigil for testing; currently I only use the Pioneer. I don't know if I can use them; I haven't tried it.\n\nAffiliation disclosure:\n- Alt of existing player: No\n- Member of another alliance: No\n\nRequirements confirmed:\n- ✅ All characters added to website (including ones not joining)\n- ✅ Agree to alliance values",
    "status": "accepted",
    "discord_thread_id": 1541852632824545361,
    "created_at": "2026-08-25T16:51:53.902000+00:00",
    "updated_at": "2026-08-27T11:34:29.667000+00:00"
  },
  {
    "id": 2073,
    "user_id": 3706,
    "corporation_id": 98838663,
    "description": "Looking for industrial corporation that accepts new players and is active in galaxy.\n\nQuestionnaire:\n- Timezone: Atlantic/Azores (GMT+0) — Europe region, evenings → EUTZ\n- Roles interested in: Resource harvesting (mining, planet harvesting, etc), Production (building things)\n- Doctrine ships: PI Hauler ships\n\nAffiliation disclosure:\n- Alt of existing player: Yes (main character: Gray Vixen)\n- Member of another alliance: No\n\nRequirements confirmed:\n- ✅ All characters added to website (including ones not joining)\n- ✅ Agree to alliance values",
    "status": "accepted",
    "discord_thread_id": 1542239253851803809,
    "created_at": "2026-08-26T18:28:11.538000+00:00",
    "updated_at": "2026-08-26T22:53:23.645000+00:00"
  },
  {
    "id": 2078,
    "user_id": 4005,
    "corporation_id": 98838663,
    "description": "Been out rock chomping on belts around Nakugard alongside M-EXEC pilots who suggested I join up. I am a returning player and primarily enjoy fleet mining ops in high sec and wormhole space.\n\nQuestionnaire:\n- Timezone: Australia/Sydney (GMT+10) — Asia-Pacific region, evenings → AUTZ\n- Roles interested in: Fleet support (painting, tackling, etc), Resource harvesting (mining, planet harvesting, etc), Production (building things)\n- Doctrine ships: Currently returning to the game, flying a pioneer (High Sec) and Venture (Wormhole). Still working up the ladder of Minmatar ships, just to cruiser level so far on Security Agent missions.\n\nAffiliation disclosure:\n- Alt of existing player: No\n- Member of another alliance: No\n\nRequirements confirmed:\n- ✅ All characters added to website (including ones not joining)\n- ✅ Agree to alliance values",
    "status": "accepted",
    "discord_thread_id": 1542679596741165177,
    "created_at": "2026-08-27T23:37:57.464000+00:00",
    "updated_at": "2026-08-30T05:49:52.024000+00:00"
  },
  {
    "id": 2101,
    "user_id": 4057,
    "corporation_id": 98838663,
    "description": "Industry with a purpose for Minmatar\n\nQuestionnaire:\n- Timezone: America/New_York (EDT) — US region, evenings → USTZ\n- Roles interested in: Fleet logistics (healing), Resource harvesting (mining, planet harvesting, etc), Production (building things)\n- Doctrine ships: None I was hoping to just do industry with the Minmatar Extraction Company\n\nAffiliation disclosure:\n- Alt of existing player: No\n- Member of another alliance: No\n\nRequirements confirmed:\n- ✅ All characters added to website (including ones not joining)\n- ✅ Agree to alliance values",
    "status": "accepted",
    "discord_thread_id": 1544144900252237885,
    "created_at": "2026-09-01T00:40:33.045000+00:00",
    "updated_at": "2026-09-03T08:10:04.699000+00:00"
  },
  {
    "id": 2102,
    "user_id": 4057,
    "corporation_id": 98838663,
    "description": "For industry with a purpose, I want to assist the front lines of the faction.\n\nQuestionnaire:\n- Timezone: America/New_York (EDT) — US region, evenings → USTZ\n- Roles interested in: Fleet logistics (healing), Resource harvesting (mining, planet harvesting, etc), Production (building things)\n- Doctrine ships: none but willing to work towards it, mostly focused on industry\n\nAffiliation disclosure:\n- Alt of existing player: No\n- Member of another alliance: No\n\nRequirements confirmed:\n- ✅ All characters added to website (including ones not joining)\n- ✅ Agree to alliance values",
    "status": "accepted",
    "discord_thread_id": 1544145555846860820,
    "created_at": "2026-09-01T00:43:09.351000+00:00",
    "updated_at": "2026-09-03T08:12:30.007000+00:00"
  },
  {
    "id": 2105,
    "user_id": 4053,
    "corporation_id": 98838663,
    "description": "Professional, and laid back.   Great amount of information\n\nQuestionnaire:\n- Timezone: Europe/London (GMT+1) — Europe region, evenings → EUTZ\n- Roles interested in: Resource harvesting (mining, planet harvesting, etc), Production (building things)\n- Doctrine ships: Everything, (apart from mining destroyers - didn't exist when I started down industry)\n\nAffiliation disclosure:\n- Alt of existing player: No\n- Member of another alliance: No\n\nRequirements confirmed:\n- ✅ All characters added to website (including ones not joining)\n- ✅ Agree to alliance values",
    "status": "accepted",
    "discord_thread_id": 1544322057448198244,
    "created_at": "2026-09-01T12:24:30.612000+00:00",
    "updated_at": "2026-09-02T23:34:03.565000+00:00"
  },
  {
    "id": 2107,
    "user_id": 4063,
    "corporation_id": 98838663,
    "description": "The described content and participation amounts in the evejobs post.\n\nQuestionnaire:\n- Timezone: America/Winnipeg (CDT) — US region, evenings → USTZ\n- Roles interested in: Resource harvesting (mining, planet harvesting, etc), Production (building things)\n- Doctrine ships: Most of the minmatar T1 up to battleships and working on caldari up to battle ships. Focused on missiles.\n\nAffiliation disclosure:\n- Alt of existing player: No\n- Member of another alliance: Yes (Eve Uni)\n\nRequirements confirmed:\n- ✅ All characters added to website (including ones not joining)\n- ✅ Agree to alliance values",
    "status": "accepted",
    "discord_thread_id": 1544428031299297342,
    "created_at": "2026-09-01T19:25:36.747000+00:00",
    "updated_at": "2026-09-03T08:12:02.739000+00:00"
  },
  {
    "id": 2110,
    "user_id": 4069,
    "corporation_id": 98838663,
    "description": "Returning to EO after 11 years, figure to get involve with the FW scene\n\nQuestionnaire:\n- Timezone: America/Chicago (CDT) — US region, mornings → AUTZ - EUTZ\n- Roles interested in: Resource harvesting (mining, planet harvesting, etc)\n- Doctrine ships: At the present time, none\n\nAffiliation disclosure:\n- Alt of existing player: Yes (main character: Azure Ronin)\n- Member of another alliance: No\n\nRequirements confirmed:\n- ✅ All characters added to website (including ones not joining)\n- ✅ Agree to alliance values",
    "status": "accepted",
    "discord_thread_id": 1544695904538329138,
    "created_at": "2026-09-02T13:10:02.704000+00:00",
    "updated_at": "2026-09-05T03:33:08.526000+00:00"
  },
  {
    "id": 2111,
    "user_id": 4071,
    "corporation_id": 98838663,
    "description": "long time miner...returning player, ran into one of your corp mates and started asking questions..\n\nQuestionnaire:\n- Timezone: America/New_York (EDT) — US region, mornings → AUTZ - EUTZ\n- Roles interested in: Resource harvesting (mining, planet harvesting, etc), Production (building things)\n- Doctrine ships: Newer pilot but willing to skill into anything that is needed.\n\nAffiliation disclosure:\n- Alt of existing player: No\n- Member of another alliance: No\n\nRequirements confirmed:\n- ✅ All characters added to website (including ones not joining)\n- ✅ Agree to alliance values",
    "status": "accepted",
    "discord_thread_id": 1544755135811559424,
    "created_at": "2026-09-02T17:05:24.540000+00:00",
    "updated_at": "2026-09-06T05:02:32.192000+00:00"
  },
  {
    "id": 2118,
    "user_id": 4095,
    "corporation_id": 98838663,
    "description": "Values seem chill. im new and looking for my first org.\n\nQuestionnaire:\n- Timezone: Australia/Sydney (GMT+10) — Asia-Pacific region, evenings → AUTZ\n- Roles interested in: Fleet damage (guns, missiles, etc), Solo combat, Small gang combat (<10 pilots), Resource harvesting (mining, planet harvesting, etc)\n- Doctrine ships: Any required\n\nAffiliation disclosure:\n- Alt of existing player: No\n- Member of another alliance: No\n\nRequirements confirmed:\n- ✅ All characters added to website (including ones not joining)\n- ✅ Agree to alliance values",
    "status": "accepted",
    "discord_thread_id": 1545541183730614394,
    "created_at": "2026-09-04T21:08:52.968000+00:00",
    "updated_at": "2026-09-06T17:43:22.880000+00:00"
  },
  {
    "id": 2126,
    "user_id": 4108,
    "corporation_id": 98838663,
    "description": "I thought doing some fleet mining could be interesting and your corp info mentions activities close to where I am currently based. Also your website is dope.\n\nQuestionnaire:\n- Timezone: America/Chicago (CDT) — US region, afternoons → EUTZ - USTZ\n- Roles interested in: Resource harvesting (mining, planet harvesting, etc), Production (building things)\n- Doctrine ships: Ive got a lot of PVE exp in the navy osprey... I am currently training exhumers to lvl 4 mastery.\n\nAffiliation disclosure:\n- Alt of existing player: No\n- Member of another alliance: No\n\nRequirements confirmed:\n- ✅ All characters added to website (including ones not joining)\n- ✅ Agree to alliance values",
    "status": "accepted",
    "discord_thread_id": 1546237296653631701,
    "created_at": "2026-09-06T19:14:59.222000+00:00",
    "updated_at": "2026-09-07T12:56:43.706000+00:00"
  },
  {
    "id": 2127,
    "user_id": 3833,
    "corporation_id": 98838663,
    "description": "I like the idea of getting into industry with the goal of producing fun and content rather than just isk\n\nQuestionnaire:\n- Timezone: America/Los_Angeles (PDT) — US region, afternoons → EUTZ - USTZ\n- Roles interested in: Resource harvesting (mining, planet harvesting, etc), Production (building things)\n- Doctrine ships: Barges and Pioneers\n\nAffiliation disclosure:\n- Alt of existing player: No\n- Member of another alliance: Yes (Eve-Scout)\n\nRequirements confirmed:\n- ✅ All characters added to website (including ones not joining)\n- ✅ Agree to alliance values",
    "status": "accepted",
    "discord_thread_id": 1546641916244922469,
    "created_at": "2026-09-07T22:02:48.050000+00:00",
    "updated_at": "2026-09-11T18:14:13.753000+00:00"
  },
  {
    "id": 2130,
    "user_id": 4116,
    "corporation_id": 98838663,
    "description": "Its been a few years since I've done mining and this group looks a good opportunity to get back into without a lot of extra stress and keeping to my real life obligations.\n\nQuestionnaire:\n- Timezone: America/Denver (MDT) — US region, evenings → USTZ\n- Roles interested in: Fleet damage (guns, missiles, etc), Fleet logistics (healing), Fleet support (painting, tackling, etc), Solo combat, Small gang combat (<10 pilots), Resource harvesting (mining, planet harvesting, etc), Production (building things)\n- Doctrine ships: I used to fly with Pandemic Horde which was armor focused, between my various toons I can fly a few mining barges but also many different armor ships from Frig to Capitals and various supports.\n\nAffiliation disclosure:\n- Alt of existing player: No\n- Member of another alliance: No\n\nRequirements confirmed:\n- ✅ All characters added to website (including ones not joining)\n- ✅ Agree to alliance values",
    "status": "accepted",
    "discord_thread_id": 1546807983151783966,
    "created_at": "2026-09-08T09:02:41.486000+00:00",
    "updated_at": "2026-09-11T07:41:25.476000+00:00"
  },
  {
    "id": 2133,
    "user_id": 4121,
    "corporation_id": 98838663,
    "description": "I'm looking for a \"simple\" mining corp that has a workflow to help the greater good.  The idea that my work isn't going straight to the market, but to help the war effort is an enticing feeling.\n\nQuestionnaire:\n- Timezone: America/New_York (EDT) — US region, evenings → USTZ\n- Roles interested in: Resource harvesting (mining, planet harvesting, etc)\n- Doctrine ships: Will be able to fly a Tempest in > 1 Day. Can fly Osprey.  Able and interested in flying a Porp.\n\nAffiliation disclosure:\n- Alt of existing player: No\n- Member of another alliance: No\n\nRequirements confirmed:\n- ✅ All characters added to website (including ones not joining)\n- ✅ Agree to alliance values",
    "status": "accepted",
    "discord_thread_id": 1546965159048781935,
    "created_at": "2026-09-08T19:27:15.140000+00:00",
    "updated_at": "2026-09-09T13:17:55.755000+00:00"
  },
  {
    "id": 2134,
    "user_id": 3952,
    "corporation_id": 98838663,
    "description": "The propaganda from FL33T on Reddit and then seeing your interactions and discussion with people in the public channels on Discord. I was also suggested when I first inquired about being a busy dad that there was space even for the \"mining at work\" people!\n\nQuestionnaire:\n- Timezone: America/Chicago (CDT) — US region, evenings → USTZ\n- Roles interested in: Fleet damage (guns, missiles, etc), Fleet logistics (healing), Fleet support (painting, tackling, etc), Solo combat, Small gang combat (<10 pilots), Resource harvesting (mining, planet harvesting, etc), Production (building things)\n- Doctrine ships: All T2 Frigates, T2/T3 Destroyers, T1 Cruisers, Minmatar T2/T3 Cruisers, T1 Battlecruisers, Minmatar T2 Battlecruisers, T1 Battleships with T1 Guns, Mining Frigates (T1/T2), Mining Destroyers (T1), Prospect, Retriever\n\nAffiliation disclosure:\n- Alt of existing player: No\n- Member of another alliance: No\n\nRequirements confirmed:\n- ✅ All characters added to website (including ones not joining)\n- ✅ Agree to alliance values",
    "status": "accepted",
    "discord_thread_id": 1547009434558136340,
    "created_at": "2026-09-08T22:23:11.244000+00:00",
    "updated_at": "2026-09-09T13:17:26.464000+00:00"
  },
  {
    "id": 2138,
    "user_id": 4149,
    "corporation_id": 98838663,
    "description": "https://my.minmatar.org/alliance/values/\n\nQuestionnaire:\n- Timezone: America/New_York (EDT) — US region, mornings → AUTZ - EUTZ\n- Roles interested in: Fleet logistics (healing), Fleet support (painting, tackling, etc), Resource harvesting (mining, planet harvesting, etc), Production (building things)\n- Doctrine ships: pioneer, slasher, vigil\n\nAffiliation disclosure:\n- Alt of existing player: No\n- Member of another alliance: No\n\nRequirements confirmed:\n- ✅ All characters added to website (including ones not joining)\n- ✅ Agree to alliance values",
    "status": "accepted",
    "discord_thread_id": 1547651722107945041,
    "created_at": "2026-09-10T16:55:24.529000+00:00",
    "updated_at": "2026-09-14T22:34:07.070000+00:00"
  },
  {
    "id": 2143,
    "user_id": 4151,
    "corporation_id": 98838663,
    "description": "A bit of everything, I have heard of Fl33t on and off since returning around 2 years ago. The Values you have fit with my feelings about the game and a team ethos is something I enjoy.\nI feel I can bring some experience and enjoy facilitating others making isk as part of a group rather than alone\n\nQuestionnaire:\n- Timezone: Europe/London (GMT+1) — Europe region, evenings → EUTZ\n- Roles interested in: Fleet damage (guns, missiles, etc), Fleet logistics (healing), Fleet support (painting, tackling, etc), Solo combat, Small gang combat (<10 pilots), Resource harvesting (mining, planet harvesting, etc), Production (building things)\n- Doctrine ships: I have 8 Characters across 4 accounts. All 8 can Fly Barges/Exhumers. Orca Pilots included.\n1 Also has most PVP skills but can fill in gaps as needed.\n\nAffiliation disclosure:\n- Alt of existing player: No\n- Member of another alliance: Yes (SEKER Matar/ SEKER Acadamy)\n\nRequirements confirmed:\n- ✅ All characters added to website (including ones not joining)\n- ✅ Agree to alliance values",
    "status": "accepted",
    "discord_thread_id": 1547996529954918540,
    "created_at": "2026-09-11T15:45:33.126000+00:00",
    "updated_at": "2026-09-11T16:51:08.170000+00:00"
  },
  {
    "id": 2147,
    "user_id": 4158,
    "corporation_id": 98838663,
    "description": "Content\n\nQuestionnaire:\n- Timezone: America/New_York (EDT) — US region, afternoons → EUTZ - USTZ\n- Roles interested in: Fleet logistics (healing), Fleet support (painting, tackling, etc), Resource harvesting (mining, planet harvesting, etc), Production (building things)\n- Doctrine ships: All\n\nAffiliation disclosure:\n- Alt of existing player: No\n- Member of another alliance: No\n\nRequirements confirmed:\n- ✅ All characters added to website (including ones not joining)\n- ✅ Agree to alliance values",
    "status": "accepted",
    "discord_thread_id": 1548401615390646282,
    "created_at": "2026-09-12T18:35:13.020000+00:00",
    "updated_at": "2026-09-14T19:41:47.546000+00:00"
  },
  {
    "id": 2148,
    "user_id": 3563,
    "corporation_id": 98838663,
    "description": "I am in L3ARN and spoke with Keldor. SInce I want to make mining my main goal I am moving to M-EXC\n\nQuestionnaire:\n- Timezone: America/Los_Angeles (PDT) — US region, evenings → USTZ\n- Roles interested in: Resource harvesting (mining, planet harvesting, etc)\n- Doctrine ships: All mining ships including exhumers, porpoise, and orca.\n\nAffiliation disclosure:\n- Alt of existing player: No\n- Member of another alliance: No\n\nRequirements confirmed:\n- ✅ All characters added to website (including ones not joining)\n- ✅ Agree to alliance values",
    "status": "accepted",
    "discord_thread_id": 1548407502440370246,
    "created_at": "2026-09-12T18:58:36.602000+00:00",
    "updated_at": "2026-09-14T19:42:01.891000+00:00"
  },
  {
    "id": 2155,
    "user_id": 4173,
    "corporation_id": 98838663,
    "description": "Hey,\nI've been a part of a couple mining outings with Hindukur Ronuken (He's a good recruiter) and I had some fun. Ive also been lucky enough to be invited to a mining fleet of yours, on Sep 15th. I'd be very appreciative of the chance to join some more going forward! Thanks for the consideration\n\nQuestionnaire:\n- Timezone: Europe/London (GMT+1) — Europe region, evenings → EUTZ\n- Roles interested in: Fleet logistics (healing), Fleet support (painting, tackling, etc), Resource harvesting (mining, planet harvesting, etc), Production (building things)\n- Doctrine ships: Pioneer, Venture, the navy version of each\n\nAffiliation disclosure:\n- Alt of existing player: No\n- Member of another alliance: No\n\nRequirements confirmed:\n- ✅ All characters added to website (including ones not joining)\n- ✅ Agree to alliance values",
    "status": "accepted",
    "discord_thread_id": 1549528298894397450,
    "created_at": "2026-09-15T21:12:15.300000+00:00",
    "updated_at": "2026-09-16T19:59:27.502000+00:00"
  },
  {
    "id": 2167,
    "user_id": 4211,
    "corporation_id": 98838663,
    "description": "I reached out on Reddit looking for a good active Corp especially since I mine and high SEC primarily\n\nQuestionnaire:\n- Timezone: America/Edmonton (MDT) — US region, mornings → AUTZ - EUTZ\n- Roles interested in: Fleet support (painting, tackling, etc), Resource harvesting (mining, planet harvesting, etc), Production (building things)\n- Doctrine ships: Non but can quickly as i need miniature skills  thats it\n\nAffiliation disclosure:\n- Alt of existing player: No\n- Member of another alliance: No\n\nRequirements confirmed:\n- ✅ All characters added to website (including ones not joining)\n- ✅ Agree to alliance values",
    "status": "accepted",
    "discord_thread_id": 1551656775013634270,
    "created_at": "2026-09-21T18:10:03.552000+00:00",
    "updated_at": "2026-09-21T23:53:09.036000+00:00"
  }
]"""


def restore_deleted_applications(apps, schema_editor):
    Application = apps.get_model("applications", "EveCorporationApplication")
    User = apps.get_model("auth", "User")
    rows = json.loads(SNAPSHOT)
    pending = []
    for row in rows:
        if Application.objects.filter(pk=row["id"]).exists():
            continue
        if not User.objects.filter(pk=row["user_id"]).exists():
            continue
        pending.append(row)
    if not pending:
        return
    Application.objects.bulk_create(
        [
            Application(
                id=row["id"],
                user_id=row["user_id"],
                corporation_id=row["corporation_id"],
                description=row["description"],
                status=row["status"],
                discord_thread_id=row["discord_thread_id"],
                processed_by_id=None,
            )
            for row in pending
        ]
    )
    for row in pending:
        Application.objects.filter(pk=row["id"]).update(
            created_at=parse_datetime(row["created_at"]),
            updated_at=parse_datetime(row["updated_at"]),
        )


def reverse_restore(apps, schema_editor):
    Application = apps.get_model("applications", "EveCorporationApplication")
    for row in json.loads(SNAPSHOT):
        Application.objects.filter(
            pk=row["id"],
            discord_thread_id=row["discord_thread_id"],
        ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("applications", "0004_alter_evecorporationapplication_processed_by"),
    ]

    operations = [
        migrations.RunPython(restore_deleted_applications, reverse_restore),
    ]
