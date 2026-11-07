---
name: town-hall-highlights
description: >-
  Produce a ~15 minute public highlights video from a longer town hall stage
  recording: slide-numbered transcript, cut list, deck stills, and a YouTube
  package. Use when the user asks for town hall highlights, a highlights cut,
  or a public video from a stage recording and deck.
---

# Town Hall Highlights

Produce a ~15 minute public highlights video from a longer stage recording. Assume the skill file, the cut, the transcript, and the upload copy will be read by anyone, including rivals. Keep operational gossip, unreleased numbers, and named-hostile color out of durable artifacts (this skill included).

## Inputs

Copy (do not move or delete) into the working folder:

- The stage recording (video preferred).
- The presented deck as PDF and, if available, PPTX.
- Optional: chat export from the same session (minute-resolution is fine).

If several candidate recordings or decks exist, list them and ask. Match the deck page count to the PDF that was on screen.

The deck file you are handed is often an earlier draft. Look for loose slide PNGs exported next to it (inserted or updated slides) and confirm every recording frame matches a still before building. A PPTX renders cleanly with headless LibreOffice once a Calibri-metric font (Carlito) is installed. If the recording is low-res (a 360p download is fine), it only drives the timeline. The picture comes from the stills.

## Outputs

- Timestamped transcript grouped by deck slide number (not video-keyframe order).
- Optional transcript with chat interleaved, plus a machine-readable slide timeline and chat timeline (seconds in the recording).
- Per-slide PNG stills from the PDF at 1920×1080 (or native 16:9), used as the picture — not the screenshare.
- Highlights cut (~14:45–15:15 unless asked otherwise), cut list, and a short review note.
- YouTube title, description with chapter times for the cut, and a 16:9 thumbnail in the org’s brand colors.
- Subtitles (SRT + VTT) timed to the cut, not the source, if requested.

Post highlights + full recording + transcript together. Jump marks are editorial, not concealment. Do not use copy like “remarks skipped,” “omitted,” or “removed.”

## Pipeline

### 1. Ingest and timelines

- Transcribe the source with word timestamps. Write segments to disk as they arrive (JSONL) so a GPU crash resumes from the last segment instead of losing a 30-minute run. Calibrate recording 0:00 to wall clock from on-screen clocks or chat reactions, not file mtime.
- Detect slide changes; match keyframes to deck PNGs by image similarity and title. Measure the slide box inside the screenshare first (row/column brightness profile); a few pixels of browser chrome in the crop drops correlation from ~1.0 to noise. Sample every 2 s, then refine each change to 0.2 s. Number everything with deck slide numbers. Note slides never shown and slides shown twice.
- If chat exists, interleave messages at estimated recording time (±1 min if the export is minute-only). Mark where speakers answer chat. Attachments with no text stay as [image].
- Speakers may be unlabeled; note likely hosts from context. Fix proper nouns against the deck and chat — ASR will mangle them.

### 2. What to keep vs cut

Propose a cut list before rendering. Split:

- **Safe:** setup over gameplay, dead air, false restarts, “um” between complete clauses, mute-wait, chat jokes the viewer cannot see, silent tail.
- **Judgment:** gossip about other groups, named-person drama, roll calls, recruiting plugs, asides. Keep if it is a real operational beat that later slides need; otherwise drop.

Keep the spine: census/state, guidance for the coming period, how to participate in industry/mining/logistics, strategy slide (“what this means for us”), and Q&A answers that members need (logistics, reimbursement, campaign status).

Geopolitics / news: introduce the factual groups or deployments that tee up the strategy slide. Jump over backup rumors, dunking, and named-person snark. One factual sentence for a deployment is enough; do not keep the roast.

Snap every cut to a sentence or clause boundary inside a measured pause. Never splice mid-word. If a planned cut would break a sentence, shrink it. ~20–40 ms fades at each join.

Write the cut list as phrase anchors (start phrase → end phrase) resolved against the word list, not raw seconds. Phrases survive a re-transcription; times do not.

Do not trust Whisper word times at a cut. Before a pause it ends words early, and it often butts the next word against the last one, so a cut on the timestamp clips the tail ("tribes" → "try") or keeps a fragment of the next word. Energy thresholds alone cannot separate a trailing syllable from the next word in connected speech. What works: run a forced aligner (wav2vec2 / torchaudio MMS_FA, CPU is fine) on a short window around each boundary, cut ~0.1 s after the aligned end and ~0.06 s before the aligned start, never past the neighbouring word. Align each boundary from two overlapping windows; if they disagree by more than 0.3 s, fall back to the waveform for that word.

Joins butt together. Speakers are on push-to-talk, so an inserted pause or room-tone fill reads as an odd breath or a dropout. Keep only the sliver of each piece's own audio at its edges.

Target length may land 14:45–15:15. Extra obvious filler is allowed if the spine survives.

Do not trim the community out to hit the number. Members watch for each other: keep the census walk-through (who grew, which corps are solid), the current campaign status, the chiefs' asks, and the moments that got a laugh in the room (a miners-kill-an-Orca story, a ribbing answer in Q&A). Cut the length from repeated points, long how-to explanations, and setup instead. Running a minute over with these in is better than 15:00 without them.

### 3. Picture and overlays

Rebuild the cut on clean deck stills, timed from the shifted slide timeline. Hides jump cuts and OBS/game chrome.

Corrections / new intel: a box at the bottom of that segment. Do not strikethrough slide text.

Jump language (whole cut, not one section):

- Removed speech ≥ 8 s: ~2 s bottom-right alert over the next slide, “Skipped ahead 42 seconds” (or “1 min 12 sec”), counted in source time.
- Shorter content jumps: ~1.2 s bottom-right alert, “On to the next point.”
- Fillers-only and silence trims: unmarked.

Alerts overlay the picture and add no time. A full-frame card with its own second of audio feels like the video stopped. Alerts must be long enough to read; an 8–12 frame flash is invisible.

Optional 2 s end card only if asked: “Full recording and transcript posted with this video.”

### 4. Render bar

- 1920×1080, 30 fps CFR, still-image x264 CRF ≤ 18.
- Tag color explicitly (BT.709 / limited range) so players and YouTube do not guess. Untagged HD often shifts brand red.
- Audio: keep source sample rate; AAC ≥ 192 kbps; about −16 LUFS, true peak under −1.5 dBTP; one AAC encode; mux video with audio copy. Two-pass loudnorm alone lands near −1 dBTP after AAC; put a limiter (~−2.5 dBFS) between loudnorm and the encode.
- Stills: normalise every PNG to 1920×1080 RGB before the concat demuxer (mixed sizes break it), quantise durations to frames cumulatively so audio and picture stay in sync over 60+ joins. On ffmpeg 4.x use `-vsync cfr`, not `-fps_mode`.
- Do not promise “denoise game bed with zero voice change.” Discord already gates noise. A wet speech isolator will color esses and room. Offer a 30 s A/B or leave the bed.

### 5. Verify

Re-transcribe the output. Every join: complete sentence either side, no clicks (sample step below local p99.9), no clipped syllables. Read the output transcript end to end for clipped tails (a word turning into a shorter one, “ships” → “shit”) and stray fragments (“…on leave which but”); both mean a boundary needs aligning. After a single change, re-transcribe just that stretch of the output. Spot-check slide vs speech at changes. Confirm the spine is still in the transcript. Duration in window. Fix color tags if a player would decode the brand red wrong.

### 6. YouTube package

- Title: org + “Town Hall #N” + month + “highlights” + 1–3 topic words. No leaking numbers or names of other groups.
- Description: date, that this is highlights, that full video and transcript are posted with it, hosts if they are public speakers, chapter times from the cut.
- Thumbnail 16:9: keep the series look so the channel reads as one set: brand red, white fist logo, heavy white “TOWN HALL / #N / MON YYYY”, gold HIGHLIGHTS tag. Vary the background per episode (e.g. the title slide's ship art duotoned into the red, fading in behind the type) rather than flat colour. Keep the tag clear of the bottom-right corner, where YouTube's duration badge sits. Huge type. No screenshots of intel slides.

## Public-safety filter

Never put in the skill, the YouTube text, or a “learnings” doc:

- Hostile or neighbor group names, FC names, or “who will batphone whom”
- Unreleased metrics, fits, timers, or reimbursement exceptions
- Drama about named members
- Internal channel names, unlisted Discord IDs, or download paths

Those belong in a private cut-review for editors, not in git.

## Stop

Ask before publishing if geopolitics still names other groups on-screen, or if a judgment cut would remove the only setup for a later slide. When the requester restores a cut for its value, restore it and note in the private review which previously cut lines are now public. Do not invent branding, doctrine, or strategy that was not in the recording.
