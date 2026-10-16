# CCP Third-Party Rules: Guidelines for the Minmatar Fleet Desktop App

**Date:** 2026-10-16 · **Applies to:** `desktop/` (Electron app) and any feature built on it · **Companion doc:** [overlay-technology.md](overlay-technology.md)

**Purpose.** This document lists the rules the desktop app follows so that nothing we ship can get a Minmatar Fleet pilot banned. It collects what CCP's EULA, Terms of Service, Third Party Policies and Developer License Agreement say. It adds CCP's published rulings on overlays, multiboxing tools, input broadcasting and client modification, maps each current feature to those rules, and lists the questions to put to CCP before we build the riskier features. Every quote below was copied from a page fetched on 2026-10-16. Where a source could not be found or confirmed, the document says so.

> **Not legal advice.** CCP has the final say: *"We cannot publish a comprehensive list of allowed and prohibited configurations"* ([S4]). Their own guidance for uncertainty is *"please refrain from using this application"* ([S4]). Re-check the sources below before shipping any new feature that touches the EVE client, its files or its windows, and open a support ticket when a feature lands in a grey area.

The EVE support site now also carries the name **Fenris** (e.g. "Fenris Bible", "About Fenris" in the footer). The legal documents still name **CCP hf.**, so this document says "CCP".

---

## 1. Rules we follow

Each rule names its source; IDs refer to the [Sources](#7-sources) list.

**Never touch the client**

1. **No input to any EVE client.** We never call `SendInput`, `keybd_event`, `PostMessage`/`SendMessage` with input messages, or anything else that produces keystrokes or clicks in an EVE window, including clicks "through" an overlay or thumbnail. Clicks that pass through our click-through windows are the player's own clicks, routed by Windows. CCP: tools that *"interact with the client (sending data/keystrokes to the client window)… are not allowed"* ([S10]); EULA §6.A ([S1]).
2. **No automation of gameplay.** No timers, triggers, scripts or "if X then do Y" behaviour that acts in the game. Alerts may only inform a human. Botting is *"the use of any third-party software or any macros, stored rapid keystrokes or other patterns that give you any in-game advantage"* ([S5]); EULA §6.A ([S1]); input automation is *"strictly prohibited"* ([S8]).
3. **No input broadcasting or multiplexing.** One player action produces at most one action in one client. The only things we may do across several clients at once are the conveniences CCP lists: *"EVE Online client settings"*, *"Window positions and arrangements"*, *"The login process"* ([S8]). Anything with *"consequences in the EVE universe"* (ships, modules, movement, items, interaction with other characters) is banned whether done *"through use of software or modified hardware"* ([S8]).
4. **Nothing inside `exefile.exe`.** No DLL injection, no in-context hooks, no DirectX/DXGI `Present` hooks, no memory reads or writes, no patching. Windows hooks must be out-of-process only: `SetWinEventHook` with `WINEVENT_OUTOFCONTEXT` and a NULL module handle. With `WINEVENT_INCONTEXT`, *"The DLL that contains the callback function is mapped into the address space of the process that generates the event"* ([S28]). If we ever add a global hotkey hook, use `WH_KEYBOARD_LL`, which *"is not injected into another process"* ([S29]). Sources: [S10] (*"do inject anything into the clients memory"*), [S3] (*"Client modification is strictly prohibited"*), [S7] (client modification means a permanent ban).
5. **Never read the client's pixels.** No screenshots, screen capture, OCR, colour sampling or image analysis of an EVE window, including reading back our own blurred background. The blur is done by the Windows compositor and must stay display-only. CCP bans tools that *"extract or try to interpret any information from within the clients window"* ([S10]).
6. **No packet sniffing, cache scraping or reverse engineering of client files or resources.** Use ESI, the SDE and the Image Server for game data and art. EULA §9.C ([S1]); *"Our EULA does not permit the scraping of the EVE Online cache"* ([S3]).
7. **No pieces of other clients over a client.** If we ever show client previews, they must be the *"full, unchanged, EVE Client instance in a view only mode"*. No cropping to the overview, Local or any other region, and no acting through the preview ([S9], [S10]).
8. **Ask CCP before building real-time cross-client features.** Showing one character's live game state (combat log, Local, scram alerts) over another character's client may recreate the effect CCP banned in 2016: *"real time intel from all those other game instances without having to switch to the other windows"* ([S9]). See [§5](#5-grey-areas-and-open-questions).
9. **CCP's local files are read-only.** We open logs and settings for reading only, never write, rename, delete or lock them, and never hold them in a way that blocks EVE. Changing client settings files is not part of the app. Any future "copy settings" feature needs a CCP answer first ([§5](#5-grey-areas-and-open-questions)). Sources: EULA §6.A (*"modify any content appearing within the Game environment"*) ([S1]); CCP's own guidance only covers backing up and restoring profile folders ([S25], [S26]).

**Keep window handling to plain window management**

10. **Window management only, one-to-one.** We may detect, position, raise or switch between unmodified EVE windows. A hotkey brings exactly one window to the front and is not passed on to the game. *"window management, of unmodified/untampered EVE Client windows, is allowed"*; *"Switching between the EVE Client windows is part of regular and very welcome multiboxing"* ([S10]).
11. **Overlays stay informational and fair.** Overlays may show what a player could reasonably have anyway (fleet info, doctrines, timers, intel channels they are in, ESI data). Nothing may give an advantage the game itself does not offer. Comfort overlays *"which do not affect how the game is played"* are not policed. Anything used *"to gain any unfair advantage, or for purposes beyond its intended use"* can be actioned *"including player bans"* ([S3], [S9]).

**ESI, SSO and our backend**

12. **Be a good ESI citizen.** Send a `User-Agent` with app name, version and a contact (email strongly preferred) ([S14]). Send `X-Compatibility-Date` ([S17], [S20]). Respect `Expires`/ETag ([S14]) and rate-limit headers, and back off on `420`/`429` + `Retry-After` ([S15]). Never call ESI more often than its cache time. *"Circumventing the ESI caching can get you banned from ESI"* ([S14]). Never work around an ESI ban: *"Circumventing the ban can result in further action being taken, up to and including a permanent ban for all of your accounts"* ([S20]).
13. **SSO done the desktop way.** If the app ever talks to EVE SSO directly, use Authorization Code + PKCE, which is *"mostly aimed at mobile and desktop applications that cannot securely store the client secret"* ([S21]). Never ship a client secret in the app; CCP itself notes an author *"can't include a client ID and secret in the application (as they become public)"* ([S12]). Request the fewest scopes, and keep refresh tokens encrypted at rest.
14. **ESI write actions only on an explicit click, one request per click.** ESI is CCP's sanctioned way to *"perform actions within EVE"* ([S11] definitions), for example setting a waypoint. Rule 2 still applies: no scheduled or triggered writes.
15. **Consent before any game data leaves the PC.** Never upload log-derived data (location, chat, combat) or ESI data to our backend without the pilot's explicit, revocable opt-in. Under DLA §2.3, no Application may be used *"as a means of tracking Player information or Player activity without the express knowledge and consent of such Player"* ([S11], [S13]).
16. **Non-commercial.** No paywall or paid features. Voluntary donations may only offset costs, and use of the app must never depend on one ([S11] §4).

**Branding and IP**

17. **Notices, not impersonation.** Show the DLA proprietary notice (text in [§2.4](#24-branding-and-ip)) and the line *"This application has been created under the EVE Developer License Agreement."* ([S12]). Never present the app as CCP's ([S11] §2) and never modify or combine the EVE logo ([S11] §7, [S24]).
18. **Use only art CCP provides for apps.** Use the Image Server for portraits, logos and type renders ([S22]). Do **not** bundle EVE Sans Neue or any art, icons or sounds extracted from the client (rule 6). No licence for the font was found.
19. **Someone signs the DLA.** The ESI application our app uses must be registered by an alliance developer who has accepted the DLA and holds an EVE account in good standing ([S11] §9).

---

## 2. What the policies say

### 2.1 EULA ([S1], last updated 2026-10-13)

The EULA page is an ordered list. Section numbers below follow the EULA's own cross-references ("section 3 above", "Section 6") and CCP's Third Party Policies, which quote the same clauses as **6.A.2**, **6.A.3** and **9.C** ([S3]).

**§2 Your Account (multiboxing needs paid accounts)**
> "You may establish more than one Account for each copy of the Software licensed. You are however not allowed to play EVE by using more than one Account at the same time, unless you pay a subscription fee for each of the Accounts you intend to use for that purpose."

**§6.A Specifically Restricted Conduct**
> "You may not take any action that imposes an unreasonable or disproportionately large load on the System."

> (6.A.2) "You may not use your own or third-party software to modify any content appearing within the Game environment or change how the Game is played."

> (6.A.3) "You may not use your own or any third-party software, macros or other stored rapid keystrokes or other patterns of play that facilitate acquisition of items, currency, objects, character attributes, rank or status at an accelerated rate when compared with ordinary Game play. You may not rewrite or modify the user interface or otherwise manipulate data in any way to acquire items, currency, objects, character attributes or beneficial actions not actually acquired or achieved in the Game."

> "You may not use the Software, or any information accessible through the System, to bypass the System login architecture or create or provide any other means through which the System may be accessed and/or the Game may be played by others, as, for example, through server emulators."

**§7.D Monitoring**
> "You agree that CCP may remotely monitor your Game hardware solely for the purpose of establishing whether in playing the Game and accessing the System you are using software created or approved by CCP, or whether you are using unauthorized software created by you or a third party in contravention of Section 6."

**§9.C Specific Restrictions (interception, reverse engineering, sniffing)**
> "You may not intercept for any purpose other than playing EVE in accordance with the EULA any information accessible through the System. You may not access the System or upload, download or use information accessible through the System, other than as permitted by the EULA."

> "You may not copy (except as set forth above), distribute, rent, lease, loan, modify or create derivative works of, adapt, translate, perform, display, sublicense or transfer the Software or any documentation accompanying the Software."

> "You may not reverse engineer, disassemble or decompile, or attempt to reverse engineer or derive source code from, all or any portion of the Software, or from any information accessible through the System (including, without limitation, data packets transmitted to and from the System over the Internet), or anything incorporated therein, or analyze, decipher, "sniff" or derive code (or attempt to do any of the foregoing) from any packet stream transmitted to or from the System, whether encrypted or not, or permit any third party to do any of the same, and you hereby expressly waive any legal rights you may have to do so."

**§5.B Suspension (applies to all linked accounts)**
> "CCP may immediately, and without notice, discontinue or suspend access to the System through your Account, and any and all other Accounts that share the name, phone number, e-mail address, internet protocol address or credit card number with the discontinued or suspended Account, in the event of (i) a breach of the EULA (including the Rules of Conduct) by you or any user under your Account; …"

The EULA does not mention overlays, multiboxing, input broadcasting, log files or settings files by name. Those are covered by the policies and rulings below.

### 2.2 Terms of Service ([S2], last updated 2026-08-27)

> "You will not attempt to decipher, hack into or interfere with any transmissions to or from the EVE Online servers, nor will you try to create or use any third party add-ons, extras or tools for the game."

> "You may not create, provide or use any server emulator or other site where EVE Online may be played. You may not post or distribute emulators, software tools or utilities related to EVE Online without the express written permission of CCP."

> "You may not exploit any bug in EVE Online to gain an unfair advantage over other players."

> "You may not engage in any activity that increases the difficulty and/or expense of CCP in maintaining the EVE Online client, server, web site or other services for the benefit and enjoyment of all its users."

Read literally, the first two clauses cover all third-party tools. CCP's own Third Party Policies, the DLA and CCP's developer portal show it tolerates and licenses tools in practice (below). See open question Q5.

### 2.3 Third Party Policies, third-party-app guidance and enforcement

**Third Party Policies** ([S3], last updated 2024-07-15)
> "We will not authorize or otherwise sanction the use of any third party software."

> "We do not endorse or condone the use of player-made software or any other third party applications or software that confers an unfair benefit to players. We may, in our discretion, tolerate the use of applications or other software that simply enhance player enjoyment in a way that maintains fair gameplay. However, if any third party application or other software is used to gain any unfair advantage, or is used for purposes beyond its intended use, or if the application or other software violates other parts of the EULA, we may fully enforce our rights to prohibit such use, including player bans. Please use player-made or other third party software at your own risk."

> "Client modification is strictly prohibited, as per our EULA"

> "For instance, the use of programs that provide in-game overlays (Mumble, Teamspeak) is not something we plan to actively police at this time."

> "Our EULA does not permit the scraping of the EVE Online cache, as per EULA Paragraph 9.C" … "we may, in our sole discretion, deliver appropriate penalties for players that engage in cache scraping after 15 April 2013 (including temporary or permanent bans)."

> "Botting software — This is NOT allowed under any circumstances."

**Third party applications** ([S4], last updated 2026-10-03). This page links the Third Party Policies, the EULA, the ToS and a *"Statement on Multiboxing/Multiplexing"* (the 2014 CCP Falcon post, [S8]) as the current references.
> "In general, any use of third party tools is done entirely at your own risk and there may be severe repercussions, up to and including a permanent suspension of your account(s). We cannot publish a comprehensive list of allowed and prohibited configurations."

> "If, after reading the policies above, there is still uncertainty on the legitimacy of the application, please refrain from using this application."

**Botting** ([S5], last updated 2026-10-13)
> "Botting is the use of any third-party software or any macros, stored rapid keystrokes or other patterns that give you any in-game advantage. Any in-game data may not be modified, manipulated, or changed in any way."

> "1st offense: 3-day ban and certain limitations for the account. 2nd offense: permanent ban."

> "Macro usage is very obvious, even if the process is being concealed. The logs do in fact show a lot, and with thorough investigation it is always possible to determine whether the player patterns are unusual."

**Suspension and Ban Policy** ([S6], last updated 2026-09-25). This is the clause that covers us as authors, not only as users:
> "An immediate permanent ban of an account may result if: … f. A player has created, distributed or advertised an illegal 3rd party program (i.e. macro or cheat program) that disrupts game mechanics, is considered unfriendly or gives an unfair advantage by misusing game features in a way for which they were not intended."

### 2.4 Developer License Agreement, ESI and SSO

**Developer License Agreement** ([S11]). It is not dated on the page; the last change announced on the developer blog is from 2017-10 ([S12]). Section numbers follow the DLA's own cross-references.

> (§1, "Application") "any application software designed, deployed or administered by Developer to provide functionality for or in conjunction with EVE via ESI or any other CCP tool, whether the software is installed on an individual computer (e.g., a desktop or laptop), …"

> (§1, "Purpose") "Developer's creation, distribution, and hosting of an Application that uses the CCP Tools to access and modify the Game Data but only where the Application is used solely to enhance Player's enjoyment of EVE and only where the Application is offered for non-commercial and non-profit use…"

> (§2.3) "Developer acknowledges and agrees that no Application shall be used (a) to inject, deliver, or activate malware, worms, Trojan horses, or other bugs, (b) as a means of phishing or spamming, (c) as a means of tracking Player information or Player activity without the express knowledge and consent of such Player, (d) as a means to misappropriate a Player's in-game items or other information, or to otherwise cheat, scam, or defraud Players who subscribe to the Application, or (e) as a means of implementing a denial of service attack…"

> "CCP has the sole right to determine whether an Application falls within the Purpose or is otherwise violating Section 2.3, and CCP may terminate or restrict any licenses granted hereunder at any time…"

> "Developer acknowledges that all of the rights granted herein are limited to use at technologically and commercially reasonable levels, as determined by CCP. CCP may, at any time, impose restrictions … (e.g., limitations on the frequency or number of calls of an Application)."

> "This license to Developer does not include the right for Developer to represent itself, its organization, or its business as that of CCP nor to hold itself out to third parties as an agent of CCP."

> (§4) "Developer may not charge any fee in exchange for a Player's access to or use of the Application, or otherwise monetize or generate any revenue from the Application." Permitted exceptions: ISK, voluntary donations *"solely to offset Developer's costs … provided that use of the Application is not in any way restricted or conditioned on providing such a donation"*, and general advertising.

> (§9) "Developer represents and warrants that he or she has a validly registered EVE account in good standing…"

DLA update, 2017-10 ([S12]): *"we now recommend that application creators add a line somewhere in their application or their website stating that they have signed the agreement … An example line that would work would be "This application has been created under the EVE Developer License Agreement.""*

**ESI rules**
- Best practices ([S14]): *"All ESI requests should contain User Agent information indicating the application making the request."* Preferred contents are *"An Email Address (Strongly Preferred)"* and *"App Name with version (Strongly Preferred)"*. Also: *"Not abiding to the information transmitted can lead to your app being banned, for various time, from accessing the resources."* and *"Circumventing the ESI caching can get you banned from ESI."*
- Rate limiting ([S15], introduced by the 2025-10-07 blog [S16]): floating-window token buckets per *"rate limit group and userID pair"*. Costs are 2XX = 2 tokens, 3XX = 1, 4XX = 5, 5XX = 0, with `429` + `Retry-After` when a bucket is empty. On routes without the new limiter, the error limit allows *"at most 100 non-2xx/3xx responses per minute. After that, it will return 420s on all ESI routes"*. Guidance: *"The intention of the rate limit is to show third party developers where the line is; but please don't take it for a challenge to constantly find the line."* The 2025 blog describes the `char-location` group (`/location`, `/online`, `/ship`): *"All applications are expected to be at or below"* the 99th-percentile line, about 1 request every 2 seconds. Its rollout schedule lists the "location group" for 3 November 2025.
- Versioning ([S17], 2025-07-10): *"Always send a X-Compatibility-Date header with your requests."* Legacy routes `/status.json`, `/verify`, `/swagger.json` and others were removed on 24 March 2026 ([S18]).
- Shared resource ([S19], 2018-06-19): using `/search/` *"as a discovery mechanism will be considered abuse of the API, and will be met with bans."*
- ESI bans ([S20]): *"Circumventing the ban can result in further action being taken, up to and including a permanent ban for all of your accounts."*

**SSO** ([S21]): PKCE *"is mostly aimed at mobile and desktop applications that cannot securely store the client secret."* Also: *"the secret must be kept private"*; *"The redirect URL must be registered with the application"*; and *"This token must be kept secure, as it can be used to obtain new access tokens"* (refresh token).

**Developer conduct** ([S13], 2016-07-04): *"using any of our tools that require you to sign the Developer License Agreement to scam other players is against the terms of the developer agreement."*

### 2.5 Branding and IP

- **Required notice** (DLA §7.1, [S11]): *"© 2014 CCP hf. All rights reserved. "EVE", "EVE Online", "CCP", and all related logos and images are trademarks or registered trademarks of CCP hf."* (The DLA asks for a notice *"substantially as follows"*. The year is CCP's text; we may update it.)
- **No combining marks** (DLA §7, [S11]): *"Developer may not combine the EVE logo or any other CCP Marks with any other marks, names or symbols without first obtaining CCP's prior written consent."*
- **Quality** (DLA §7, [S11]): *"Developer shall use the CCP Tools and CCP Marks in a manner that conforms to the specifications and standards of quality that CCP prescribes from time to time."*
- **Content Creation Terms of Use** ([S24], last updated 2026-06-10). Trademarks only *"when they remain unchanged"*, and a disclaimer: *"This material is used with limited permission of CCP Games. No official affiliation or endorsement by CCP Games is stated or implied."* For apps, CCP points elsewhere: *"Due to the way third-party tools can interact with the game and the community, we have an additional set of separate guidelines and a license agreement designed with developers in mind"* (the Third Party Policy and the developer portal).
- **Images** ([S22]): Image Server at `images.evetech.net`. *"You are welcome to point your clients and applications directly at the image service and use it as a CDN."* The old Image Export Collection is marked deprecated.
- **Font:** no CCP licence or download for *EVE Sans Neue* was found. It is part of the client (the "Software"), so copying it out falls under EULA §9.C. Do not bundle it.

---

## 3. Rulings and exceptions

"Allowed" = CCP said it is fine. "Tolerated" = CCP says it won't police it but reserves the right. "Banned" = CCP said it is prohibited. "No ruling found" = nothing from CCP found during this research.

| Tool / behaviour | CCP position | Date | Source |
|---|---|---|---|
| Multiboxing (several accounts at once) | **Allowed**: *"we would like to clarify that multiboxing is allowed"* (each account must be paid, EULA §2) | 2014-11-25 | [S8], [S1] |
| Input automation (bots, macros) | **Banned**: two-strike policy. Today's Botting page: 3-day ban + limitations, then permanent. The 2014 post said 30 days, then permanent. | policed since 2013-03-15; page updated 2026-10-13 | [S5], [S8] |
| Input broadcasting / multiplexing with in-game consequences | **Banned** from 2015-01-01: *"Activation and control of ships and modules"*, *"Navigation and movement within the EVE universe"*, *"Movement of assets and items within the EVE universe"*, *"Interaction with other characters"*. Still linked as current guidance by [S4] (updated 2026-10-03). | 2014-11-25 | [S8], [S4] |
| Broadcasting for client settings, window positions, login | **Allowed**: *"actions taken that do not have an impact on the EVE universe and are carried out for convenience"* | 2014-11-25 | [S8] |
| Client modification (e.g. "Autopilot to zero") | **Banned**: *"In the future, we will be sticking to our normal policy where client modification is a permanent ban."* | 2013-04-18 | [S7], [S3] |
| Multiboxing software (ISBoxer etc.) | **Tolerated** for multiboxing only: *"unless we determine that people are doing things beyond “multiboxing”, we will not be taking any action"*. Window management with ISBoxer **allowed** without broadcasting. | 2013-04-18; 2016-02-26 | [S7], [S10] |
| Voice overlays (Mumble, TeamSpeak) | **Tolerated**: *"not something we plan to actively police at this time"* | 2013 policy; restated 2016-02-24 | [S3], [S9] |
| Chat/IM, Steam and web-browser overlays | **Tolerated**: *"We also do NOT consider it unfair if you use other comfort overlays which do not affect how the game is played. This includes overlays for chat and IM applications, the Steam overlay, and Web-Browser overlays for example."* CCP's support site also documents the Steam Overlay with EVE (2025-10-16). Discord is not named; it falls under "chat and IM applications". | 2016-02-24 | [S9], [S27] |
| Overlays using elements of other EVE clients | **Banned**: *"We do consider overlays using elements of a second or multiple other EVE clients to be against the rules."* Examples: another client's overview shown over your main; activating modules in other clients through overlays. | 2016-02-24 | [S9] |
| EVE-O Preview (full client thumbnails) | **Allowed**: *"Overlays which contain a full, unchanged, EVE Client instance in a view only mode, no matter how large or small they are scaled, like it is done by EVE-O Preview as of today, are fine with us."* (CCP Grimmi). A CCP FoxFour quote (*"Assuming the functionality of the software doesn't change, it is allowed in its current state"*) is only available via the tool's README (secondary; original post not found). | 2016-02-26 | [S10]; [S30] secondary |
| Fast window switching, tiling WMs, several monitors, clients pinned to all virtual desktops | **Allowed**: *"Switching between the EVE Client windows is part of regular and very welcome multiboxing. Being good at it is not a ban-able offense"*; *"we are not banning monitors"*; virtual desktops: *"Yes, absolutely."* | 2016-02-26 | [S10] |
| Tools that modify the client, read/interpret the client window, send data/keystrokes to it, or inject into its memory | **Banned**: *"Applications/tools that do modify the client, do extract or try to interpret any information from within the clients window, do interact with the client (sending data/keystrokes to the client window), do inject anything into the clients memory or try to interact with the client in any way which cannot be achieved without using said applications/tools, are not allowed."* | 2016-02-26 | [S10] |
| Pirates Little Helper (paste Local into a standalone app) | **Allowed**: *"a stand alone application which does not do any of the above to/with the EVE Client and we therefore do not see any reason to outlaw its usage."* By the same test, D-scan/Local paste tools that work from clipboard text are fine (our inference). | 2016-02-26 | [S10] |
| Lists of allowed tools | **None will be given**: *"We cannot sanction 3rd party programs that we do not create or have any control over. Period."* | 2016-02-26 | [S10]; also [S4] |
| EVE-X-Preview, EVE Preview Manager, other preview forks | **No ruling found.** They are covered by the EVE-O ruling only as far as they behave the same way (full, unchanged, view-only). EVE Preview Manager (Linux) is listed on CCP's developer portal, under a non-endorsement disclaimer. | — | [S23] |
| EVE-O Preview fork with in-client "Robin" DLL (FPS limiter, audio mute) | **No CCP ruling found.** A community review (2026-10-07) shows it injects into `exefile.exe` and hooks DXGI `Present`. That falls under client modification as described in [S3]/[S7]/[S10]. Shows that old rulings do not cover new features. | 2026-10-07 | [S31] secondary |
| EveVision (Electron + DLL injected overlay) | **No CCP ruling found.** The project assesses itself as allowed by the 2016 blog. Its injection contradicts [S10]'s "inject" test. Repo last pushed 2023-05-10. *The claim in overlay-technology.md that CCP "only tolerated it" could not be confirmed.* | — | [S33] secondary |
| Chat-log intel tools (RIFT, SMT, IntelPy, etc.) | **No explicit CCP ruling found.** Logs are files the client writes for the player, not the client window or memory, so the [S10] test is not triggered. RIFT and SMT are listed on CCP's developer portal ("community tools"), with *"we do not endorse or guarantee"*. IntelPy: nothing found. | listing current 2026-10 | [S23] |
| Pyfa, EVEMon | **No tool-specific ruling found.** They are standalone and ESI-based, covered by the DLA. Widely used (EVE University lists both). | — | [S11]; [S32] secondary |
| Settings managers (EVE Settings Manager, profile copiers) | **No CCP statement found** on third-party tools that copy `core_char`/`core_user` files. Related: broadcasting *"EVE Online client settings"* is allowed ([S8]). CCP's own support article tells players to copy `settings_<profile>` folders to back up and restore them ([S25]), and warns against reusing old settings files after a reset ([S26]). | — | [S8], [S25], [S26]; [S32] secondary |
| Memory reading / Sanderling-style bots | **Banned** under [S10] ("inject…", "extract… from within the clients window") and the botting rules [S5]. No Sanderling-specific statement found. EVE University: *"Many use cases for this application violate both EVE Online's EULA…"* | 2016-02-26 | [S10], [S5]; [S32] secondary |
| Screen reading / OCR of the client | **Banned**: *"extract or try to interpret any information from within the clients window"* | 2016-02-26 | [S10] |
| Cache scraping | **Banned**: penalties for scraping after 2013-04-15 | 2013-04 | [S3] |
| Client resource extraction (e.g. Phobos) | **No tool-specific statement found.** Covered by EULA §9.C (reverse engineering, *"anything incorporated therein"*) and the cache-scraping policy. Use the SDE / Image Server instead. | — | [S1], [S3] |
| Packet sniffing | **Banned**: EULA §9.C *"analyze, decipher, "sniff" … any packet stream"*; ToS *"decipher, hack into or interfere with any transmissions"* | current | [S1], [S2] |
| ESI search used for discovery | **Banned** (ESI ban) | 2018-06-19 | [S19] |
| ESI rate limiting | **In force**, rolled out by route group from 2025-10-13 to 2025-12-04 | 2025-10-07 | [S16], [S15] |
| AI / LLM tools and agents | **No CCP policy statement found (2023–2026).** The botting definition ([S5]) does not depend on technology. CCP's developer portal lists ESI-only AI assistants (e.g. "EVE AI Agent", "OpenClaw EVE ESI Skill") under its non-endorsement disclaimer. The 2026 "AI-powered fit recommendations" ESI blog posts are an April joke, not policy. | — | [S5], [S23] |

---

## 4. How our current features map to the rules

Status: **Allowed** = inside an explicit allowance. **Low risk** = no ruling, but clearly outside every prohibition. **Grey** = reasonable either way; ask CCP. **Needs care** = allowed, but a specific implementation rule must hold.

| Feature (as built in `desktop/`) | Status | Reasoning | Cite |
|---|---|---|---|
| Always-on-top, click-through, never-focused overlay windows composited by DWM (no injection, no DirectX hooks) | **Allowed** (tolerated class) | Separate OS windows, same class as voice/chat/browser comfort overlays. The client is not modified, read or sent input. Keep it that way: blur stays compositor-only (rule 5), no pixel reads, clicks are never synthesised (rule 1), content stays informational (rule 11). | [S9], [S10], [S3] |
| Foreground/EVE-window detection: `GetForegroundWindow`, `SetWinEventHook`, `EnumWindows`, `GetWindowText` ("EVE - <Character>"), `GetClientRect` | **Allowed** / needs care | Read-only OS window metadata. It reads nothing *from within* the client window and sends nothing to it. Same kind of access as window managers and EVE-O Preview, which CCP allowed. `helper.cs` registers its hooks with flags `0` (`WINEVENT_OUTOFCONTEXT`) and `2` (`OUTOFCONTEXT | SKIPOWNPROCESS`) and a NULL module, so nothing loads into `exefile.exe`. Keep it that way (rule 4). | [S10], [S28] |
| Reading `Documents\EVE\logs\Chatlogs` and `Gamelogs` (system, jumps, combat lines, intel chat) | **Low risk** for the same character; **Grey** for cross-character display | The client writes these files for the player. Reading them is not client modification, memory access or screen reading. Widely used, and log-reading tools are listed on CCP's developer portal. Two cautions: (a) showing one character's live log state over **another** character's client may count as the banned "real time intel from … other game instances" (Q2); (b) uploading any of it needs explicit opt-in (rule 15). Open files read-only (rule 9). | [S10], [S9], [S23], [S11] §2.3 |
| Reading `%LOCALAPPDATA%\CCP\EVE\…\core_char_<id>.dat` to copy `windowTransparency` | **Grey (low risk)** | Read-only, cosmetic, no in-game effect. No CCP statement covers third-party reading of settings files. Parsing CCP's file format could arguably fall under EULA §9.C *"anything incorporated therein"*. Settings are something CCP treats as convenience ([S8]), and CCP tells players to copy these folders ([S25]). Keep it read-only and non-locking. Fall back to a manual slider if CCP objects (Q1). | [S1] §9.C, [S8], [S25] |
| ESI: public `POST /universe/ids/` to resolve the window-title name to a character ID | **Allowed**, **needs care** | Licensed use of ESI. Current code (`src/main/eve_settings.js`) calls `https://esi.evetech.net/latest/universe/ids/?datasource=tranquility` with no app `User-Agent` and no `X-Compatibility-Date`. It still works (HTTP 200 on 2026-10-16), but best practice asks for both. Add them and keep the per-session cache. | [S14], [S17] |
| EVE SSO / ESI with tokens (via our backend today; possibly in the app later) | **Allowed**, needs care | Today the desktop app signs in with Discord through our backend, and EVE SSO runs server-side. If the app ever does EVE SSO itself: PKCE, no embedded secret, minimal scopes, encrypted tokens, polling no faster than cache times (`char-location` group). | [S21], [S12], [S16] |
| Fleet view in the Fleets window (FC summary, member view, form-up, ship lost, after-action) | **Allowed** | Fleet info from our backend: the tracked fleet the FC already shares through ESI, doctrines and sign-ups. Informational only (rule 11); every action is one click (copy a fit to the clipboard, sign up for a ship on our site, refresh the MOTD through our backend). "You" is the character whose client is in front, never another client's character (rule 8). The front client's system is read from its own Local log and sent only to ESI's public route API for a jump count, never to our backend (rule 15). | [S9], [S3], [S11] §2.3 |
| ESI: public `GET /route/{origin}/{destination}` and `POST /universe/ids` for jump counts | **Allowed** | Public, unauthenticated ESI with `User-Agent` and `X-Compatibility-Date`. Each pair of systems is asked once per session; ESI caches routes for 24 h (rule 12). | [S14], [S17] |
| Our own backend API (fleets, doctrines, profiles) | **Allowed** | Not a CCP service. DLA duties still apply to anything derived from ESI or the client: consent for tracking, non-commercial use. | [S11] §2.3, §4 |
| EVE-styled look (Photon-like chrome, glass) | **Allowed**, needs care (IP) | Styling our own windows is not client modification. Do not ship EVE Sans Neue or icons/art extracted from the client. Use the Image Server and show the DLA notice. Consider a small app mark in our window chrome so screenshots are never mistaken for the client UI. | [S11] §7, [S22], [S1] §9.C |

**Planned / possible features**

| Feature | Status | Conditions |
|---|---|---|
| Intel alerts from intel chat (sound, toast, overlay line) | **Low risk** | Notify only. No automatic in-game reaction (rule 2). Use channels the character has joined. |
| Showing an alt's live state (combat, scram, Local) over the main client | **Grey: ask first** | May reproduce the effect CCP banned in [S9]. Do not ship before Q2 is answered. |
| Client previews (DWM thumbnails) | **Allowed** with limits | Full, unchanged, view-only client. No cropping/zooming into parts, no clicks forwarded into the client. Clicking a thumbnail may only bring that window to the front. [S9], [S10] |
| Client-switch hotkeys / cycle groups | **Allowed** with limits | One key raises exactly one window. Consume the key (don't pass it on). `WH_KEYBOARD_LL` only. No key sequences sent to clients. [S10], [S29] |
| Anything that sends keys/clicks to several clients ("press F1 in all") | **Banned** | Input broadcasting [S8]. Don't build. |
| Copying settings between characters (writing `core_char`/`core_user`) | **Grey: ask first** | No CCP statement. Writing CCP's files is a step beyond reading them. Would need explicit backup/restore and an answer to Q4. |
| ESI write actions (set waypoint, open in-game windows) | **Allowed** | One request per user click, never scheduled or triggered (rules 2, 14). |
| Uploading location/intel from logs to the alliance backend | **Allowed with consent** | Explicit opt-in per pilot, revocable, documented (DLA §2.3(c)). Automatic relay of reports might still raise "automation" questions (Q6). |

---

## 5. Grey areas and open questions

Ask these through a CCP support ticket (support site, or `support@eveonline.com`, the EULA's notice address [S1]) before building the related features. Use the `#3rd-party-dev-and-esi` channel on the official EVE Discord ([S20] support page) for ESI-side questions. Keep any written answer in this folder.

1. **Q1: Reading client settings files.** May a third-party app read (never write) `core_char_<id>.dat` to mirror a cosmetic setting (window transparency, UI scale) in its own overlay windows?
2. **Q2: Cross-client data on an overlay.** The 2016 rule bans overlays using *elements* of other clients. Does it also cover showing data derived from another logged-in character's **log files** (combat lines, Local, jumps) over a different client? This is our biggest open risk for multi-client features.
3. **Q3: EVE-styled overlay windows and the font.** Is an overlay styled like Photon windows and pinned over the client acceptable? Can EVE Sans Neue or official UI icons be licensed for a DLA application?
4. **Q4: Settings copy (write).** What is CCP's stance on tools that copy settings files between characters/accounts (EVE Settings Manager-style)? No statement was found.
5. **Q5: ToS wording vs. DLA.** The ToS says players won't *"create or use any third party add-ons, extras or tools for the game"* and may not *"post or distribute … software tools or utilities related to EVE Online without the express written permission of CCP"*. Does distributing a DLA-registered application satisfy "express written permission", or is it tolerance only?
6. **Q6: Automated intel relay.** Is an opt-in feature that forwards intel-channel lines or the pilot's current system to the alliance backend/Discord acceptable, given DLA §2.3(c) consent and the automation rules?
7. **Q7: Current penalty for input broadcasting.** The 2014 post sets 30 days, then permanent. Today's Botting page says 3 days + limitations, then permanent, for botting. Which applies to broadcasting now? (This matters for user guidance, not for our design: we don't broadcast.)
8. **Unverified claim in a sibling doc.** overlay-technology.md says CCP "only tolerated" EveVision. No CCP statement was found. Treat that sentence as unconfirmed.

---

## 6. Re-check triggers

Re-read [S1]–[S6] and [S11] and update this document when any of these happen:
- A new feature touches EVE windows, input, client files or another client's data.
- The "last updated" date of the EULA, Third Party Policies, Botting or Third party applications page changes. Dates as fetched: 2026-10-13, 2024-07-15, 2026-10-13, 2026-10-03.
- CCP posts a security/third-party dev blog or an ESI blog that changes limits or routes.

---

## 7. Sources

All fetched on 2026-10-16. "Updated" is the page's own last-updated timestamp where available.

**Primary: CCP**
- [S1] EVE Online End User License Agreement (updated 2026-10-13): https://support.eveonline.com/hc/en-us/articles/8413329735580-EVE-Online-End-User-License-Agreement
- [S2] EVE Online Terms of Service (updated 2026-08-27): https://support.eveonline.com/hc/en-us/articles/8414770561948-EVE-Online-Terms-of-Service
- [S3] Third Party Policies (updated 2024-07-15): https://support.eveonline.com/hc/en-us/articles/8564030965660-Third-Party-Policies
- [S4] Third party applications (updated 2026-10-03): https://support.eveonline.com/hc/en-us/articles/5888034246428-Third-party-applications
- [S5] Botting (updated 2026-10-13): https://support.eveonline.com/hc/en-us/articles/7370802950172-Botting
- [S6] Suspension and Ban Policy (updated 2026-09-25): https://support.eveonline.com/hc/en-us/articles/8563815513116-Suspension-and-Ban-Policy
- [S7] CCP Stillman, "Client modification, the EULA and you" (2013-04-18): https://www.eveonline.com/news/view/client-modification-the-eula-and-you
- [S8] CCP Falcon, "Update regarding Multiboxing and input automation" (forum, 2014-11-25): https://forums-archive.eveonline.com/message/5241022/. The live archive returned HTTP 503; text read from the Wayback copy https://web.archive.org/web/20210117032302/https://forums-archive.eveonline.com/message/5241022/. [S4] links the same post (`m=5241022`) as the "Statement on Multiboxing/Multiplexing".
- [S9] Team Security, "Overlays, ISK Buyer Amnesty and Account Security" (2016-02-24): https://www.eveonline.com/news/view/overlays-isk-buyer-amnesty-and-account-security
- [S10] CCP Grimmi, Team Security answers in the dev-blog thread (forum post #336, 2016-02-26): https://forums-archive.eveonline.com/message/6362936. Read from the Wayback copy https://web.archive.org/web/20220926230005/https://forums-archive.eveonline.com/message/6362936. The thread's first post (CCP Phantom) links to it as "some answers from Team Security".
- [S11] Developer License Agreement: https://developers.eveonline.com/license-agreement
- [S12] "Updates to the Developer License Agreement – 2017-10" (2017-10-19): https://developers.eveonline.com/blog/updates-to-the-developer-license-agreement-2017-10
- [S13] CCP Bartender, "Reminder to Developers: No Scamming" (2016-07-04): https://developers.eveonline.com/blog/reminder-to-developers-no-scamming
- [S14] Best Practices for ESI: https://developers.eveonline.com/docs/services/esi/best-practices/
- [S15] ESI Rate Limiting: https://developers.eveonline.com/docs/services/esi/rate-limiting/
- [S16] "Hold your horses: introducing rate limiting to ESI" (2025-10-07, last updated 2025-12-01): https://developers.eveonline.com/blog/hold-your-horses-introducing-rate-limiting-to-esi
- [S17] "Changing versions: /v42/ was getting out of hand" (2025-07-10): https://developers.eveonline.com/blog/changing-versions-v42-was-getting-out-of-hand
- [S18] "Spring Cleaning: legacy routes removed 24 March 2026" (2026-02-24): https://developers.eveonline.com/blog/spring-cleaning-legacy-routes-removed-24-march-2026
- [S19] "The ESI API is a shared resource, do not abuse it" (2018-06-19): https://developers.eveonline.com/blog/the-esi-api-is-a-shared-resource-do-not-abuse-it
- [S20] ESI Overview (ESI bans) and Third-party developer support: https://developers.eveonline.com/docs/services/esi/overview/ · https://developers.eveonline.com/docs/support/
- [S21] Single Sign-On (SSO): https://developers.eveonline.com/docs/services/sso/
- [S22] EVE Image Server: https://developers.eveonline.com/docs/services/image-server/
- [S23] Community tools and Services (with RIFT, SMT, EVE Preview Manager pages): https://developers.eveonline.com/docs/community/ · https://developers.eveonline.com/docs/community/rift-intel-fusion-tool/ · https://developers.eveonline.com/docs/community/smt/ · https://developers.eveonline.com/docs/community/eve-preview-manager/
- [S24] EVE Online Content Creation Terms of Use (updated 2026-06-10): https://support.eveonline.com/hc/en-us/articles/8563917741084-EVE-Online-Content-Creation-Terms-of-Use
- [S25] Profile Manager (updated 2026-09-07): https://support.eveonline.com/hc/en-us/articles/5885278408860-Profile-Manager
- [S26] Clearing client settings and the client side cache data (updated 2026-09-16): https://support.eveonline.com/hc/en-us/articles/6918765073436-Clearing-client-settings-and-the-client-side-cache-data
- [S27] Using Steam Overlay with EVE Online (2025-10-16): https://support.eveonline.com/hc/en-us/articles/22992614164124-Using-Steam-Overlay-with-EVE-Online

**Primary: Microsoft (Windows API behaviour)**
- [S28] SetWinEventHook: https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwineventhook
- [S29] LowLevelKeyboardProc: https://learn.microsoft.com/en-us/windows/win32/winmsg/lowlevelkeyboardproc

**Secondary (not CCP; context only)**
- [S30] EVE-O Preview README, "EVE Online EULA/ToS" section (quotes CCP FoxFour and CCP Grimmi): https://github.com/Phrynohyas/eve-o-preview
- [S31] EveOPlus/eve-o-preview issue #44, "Robin injects code into the EVE client…" (2026-10-07): https://github.com/EveOPlus/eve-o-preview/issues/44
- [S32] EVE University Wiki, Third-party tools: https://wiki.eveuniversity.org/Third-party_tools
- [S33] EveVision README, "EULA Compliance": https://github.com/evevision/evevision

**Could not verify**
- The original CCP FoxFour post quoted in the EVE-O Preview README (author/date/thread not found).
- Any CCP statement specific to EVE-X-Preview, EveVision, Sanderling, Phobos, IntelPy, Pyfa, EVEMon or EVE settings managers.
- Any 2023–2026 CCP policy statement on AI/LLM-driven tools or a new third-party policy page. The Third Party Policies page has not changed since 2024-07-15.
- A licence for the EVE Sans Neue font.
- That Node's `fs.readFileSync`/`fs.openSync(…, 'r')` on Windows opens files with share modes that never block EVE's writes. This is believed true (libuv default) but was not checked against documentation for this report.
