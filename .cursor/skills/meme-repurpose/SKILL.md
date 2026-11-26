---
name: meme-repurpose
description: >-
  Repurpose a short-form meme video (Instagram reel, TikTok, Short) into an
  EVE / Minmatar Fleet version: download it, work out its format, track a logo
  or prop onto a character, build an EVE intro from ship renders, workshop the
  captions for the alliance, and package it for YouTube Shorts. Use when the
  user shares a reel or meme link to reuse, asks to "edit the meme format",
  put our logo on a character, make an EVE version of a meme, or write captions
  or a title for a meme video.
---

# Meme Repurpose

Turn someone else's meme format into one about the alliance, without breaking what makes the format work. This repository is public: keep campaign targets, dates and Discord details out of this skill and out of anything committed. Videos and third-party media stay in the scratchpad, never in the repo.

## Tools

`meme_tools.py` (in this folder) does the mechanical parts. Run `python3 .claude/skills/meme-repurpose/meme_tools.py <command> --help` for options.

| Command | Does |
|---|---|
| `cuts` | Prints scene-cut frame numbers |
| `sheet` | Gridded, frame-numbered contact sheets to read positions from |
| `track` | Composites an overlay onto the punchline clip along a template track |
| `cutout` | Fetches an EVE ship render and cuts it out of its background |
| `warp-intro` | Renders a fleet-in-warp intro from cutouts |
| `assemble` | Builds the finished video: setup + caption, cut, punchline + label + step captions, source audio |

Templates in `templates/` hold what was measured for a format (cut time, caption bands, scenes, tracks), so a format is measured once. `templates/pooh-piglet.json` is the "me and my dog:" / Soviet Winnie-the-Pooh reel.

## Workflow

1. **Download** with `yt-dlp -o reel.%(ext)s --write-info-json <url>` into a fresh scratchpad folder. The auto-mode classifier may block it the first time; ask the user to allow it rather than working around it. Logged-out Instagram pages carry no video URL.
2. **Understand the format** before editing. Contact-sheet it (`ffmpeg ... fps=1,scale=360:-1,tile=4x3`) and write down: the parts, where the hard cut lands (it is on the beat; keep it there), each caption's font, size and position, and what the joke is. Most two-part reels are *setup question over a clip* → *"me and X:" over a reaction clip*.
3. **Measure** once and save a template: the cut (`cuts`), the caption band and clip box (`ffmpeg cropdetect` on the punchline, then again below the caption to find where the clip starts), and per-scene frame ranges.
4. **Track** a character with keyframes. Make sheets every 4 frames (`sheet --every 4 --include <scene starts>`), read the target's position off the grid, and put keyframes per scene in the template. Interpolation inside a scene is enough. Check full-size frames from every scene afterwards.
5. **Build the intro** if the setup clip is someone else's face: `cutout` the hulls, then `warp-intro`. Or use footage the user recorded, which beats renders.
6. **Workshop the words** (below), render two or three options with `assemble`, and let the user pick.
7. **Check** a frame from each part, then send the video. Tell the user the scratchpad is cleared when the session ends.

## Making the words land

- **Keep the format's grammar.** The setup is an outsider's question in quotes; the punchline is a relationship label (`me and X:`). Replacing the label with a situation ("When it's campaign time:") breaks the joke and loses who is who.
- **The visual must refute the question.** "don't you get bored...?" answered by obvious joy works. Don't prime a negative the audience may agree with ("tired of deploying?" when people are tired).
- **Cast it.** "me" works when posted from the leader's own account; from the alliance account, name them ("<leader> and Minmatar Fleet:"). An overlay on the second character (the logo) says who they are; leave the first character unedited.
- **Use what members just lived through.** Read the recent `#announcements` and campaign channels (Discord MCP) for shared experiences: the war that just ended, the time-dilation fight, the prep checklist. The best setup was "didn't you guys literally just finish a war?", true for every member and readable by outsiders. Use themes only; never quote members by name.
- **Opsec.** If a campaign page or the town hall treats the target as undisclosed, keep the location out of the video, title and description until the move is public.
- **Step captions** ("Clean up your hangars", ...) go in the black band under the clip, one per scene that fits the action (washing up → hangars, eating → wallets, walking off → jump clones). They must not compete with the label; offer smaller or dimmer if it looks busy.
- Render options rather than describing them; people judge captions on the video.

## Lessons

- ffmpeg's scene filter missed cuts between similar painted backgrounds; `cuts` (mean frame difference) found all of them.
- Colour masks can't find a pink character in a painted cartoon (the backgrounds share its colours). Manual keyframes on gridded sheets took minutes and were reliable.
- When the character's body is hidden (behind a table), put the overlay on what is visible and fits (a napkin), or on the table next to them.
- A prop in a character's hand reads only if it is big (about 3.5× the badge) and outlined; a dark realistic render disappears on a painted background. The `--style toy` cutout adds a black and cream outline.
- EVE image server renders (`images.evetech.net/types/<id>/render`) exist for ships, not planets or suns. Check type IDs against `frontend/app/src/json/eve_sde/invTypes.json` (3071 is the Uroborus, not a sun).
- The renders show the nose at the lower left. Rotating them to point right turns them upside down; `cutout` rotates by -52° so the ship is level, nose left, and `warp-intro` runs the streaks left to right to match.
- A Pillow image made with `Image.fromarray` can share numpy's buffer, and `ImageDraw.floodfill` on it silently does nothing. Call `.copy()` first (`meme_tools.py` does).
- The alliance logo is `frontend/app/public/images/fleet-logo.png` (round, transparent). Fonts that match common meme styles: Inter Bold (sans captions), Caladea (the serif "me and my dog:" look).

## Packaging

- **YouTube Shorts title** (100 characters max): a line outsiders get without context, plus `#eveonline #shorts`. The first three hashtags in the description show above the title, so lead with `#eveonline #eve #minmatar`.
- **Description**: an in-joke first line for members, the step captions as a call to action, a link to my.minmatar.org.
- **Rights**: the reaction clip and audio belong to others. Expect a Content ID claim (ads off or revenue to the owner) rather than a takedown, and say so to the user.
