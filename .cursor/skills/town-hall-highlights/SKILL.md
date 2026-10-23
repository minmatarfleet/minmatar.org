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

- Transcribe the source with word timestamps. Calibrate recording 0:00 to wall clock from on-screen clocks or chat reactions, not file mtime.
- Detect slide changes; match keyframes to deck PNGs by image similarity and title. Number everything with deck slide numbers. Note slides never shown and slides shown twice.
- If chat exists, interleave messages at estimated recording time (±1 min if the export is minute-only). Mark where speakers answer chat. Attachments with no text stay as [image].
- Speakers may be unlabeled; note likely hosts from context. Fix proper nouns against the deck and chat — ASR will mangle them.

### 2. What to keep vs cut

Propose a cut list before rendering. Split:

- **Safe:** setup over gameplay, dead air, false restarts, “um” between complete clauses, mute-wait, chat jokes the viewer cannot see, silent tail.
- **Judgment:** gossip about other groups, named-person drama, roll calls, recruiting plugs, asides. Keep if it is a real operational beat that later slides need; otherwise drop.

Keep the spine: census/state, guidance for the coming period, how to participate in industry/mining/logistics, strategy slide (“what this means for us”), and Q&A answers that members need (logistics, reimbursement, campaign status).

Geopolitics / news: introduce the factual groups or deployments that tee up the strategy slide. Jump over backup rumors, dunking, and named-person snark. One factual sentence for a deployment is enough; do not keep the roast.

Snap every cut to a sentence or clause boundary inside a measured pause. Never splice mid-word. If a planned cut would break a sentence, shrink it. ~20–40 ms audio crossfade; leave a little room tone. Pause trims shorten gaps to a beat, not to zero.

Target length may land 14:45–15:15. Extra obvious filler is allowed if the spine survives.

### 3. Picture and overlays

Rebuild the cut on clean deck stills, timed from the shifted slide timeline. Hides jump cuts and OBS/game chrome.

Corrections / new intel: a box at the bottom of that segment. Do not strikethrough slide text.

Jump language (whole cut, not one section):

- Removed speech ≥ 8 s: ~1.0 s full-frame bump, dimmed outgoing slide, short bar, text “Skipping ahead.”
- Shorter content jumps: ~1.2 s bottom-right ping, “On to the next point.”
- Silence-only / micro-pause trims under ~1 s: unmarked.

Bumps must be long enough to read. A 8–12 frame flash is invisible — do not ship that.

Optional 2 s end card only if asked: “Full recording and transcript posted with this video.”

### 4. Render bar

- 1920×1080, 30 fps CFR, still-image x264 CRF ≤ 18.
- Tag color explicitly (BT.709 / limited range) so players and YouTube do not guess. Untagged HD often shifts brand red.
- Audio: keep source sample rate; AAC ≥ 192 kbps; about −16 LUFS, true peak under −1.5 dBTP; one AAC encode; mux video with audio copy.
- Do not promise “denoise game bed with zero voice change.” Discord already gates noise. A wet speech isolator will color esses and room. Offer a 30 s A/B or leave the bed.

### 5. Verify

Re-transcribe the output. Every join: complete sentence either side, no clicks (sample step below local p99.9), no clipped syllables. Spot-check slide vs speech at changes. Confirm the spine is still in the transcript. Duration in window. Fix color tags if a player would decode the brand red wrong.

### 6. YouTube package

- Title: org + “Town Hall #N” + month + “highlights” + 1–3 topic words. No leaking numbers or names of other groups.
- Description: date, that this is highlights, that full video and transcript are posted with it, hosts if they are public speakers, chapter times from the cut.
- Thumbnail 16:9: brand red/gold (or the org’s actual slide colors, sampled from the deck). Huge type. No screenshots of intel slides.

## Public-safety filter

Never put in the skill, the YouTube text, or a “learnings” doc:

- Hostile or neighbor group names, FC names, or “who will batphone whom”
- Unreleased metrics, fits, timers, or reimbursement exceptions
- Drama about named members
- Internal channel names, unlisted Discord IDs, or download paths

Those belong in a private cut-review for editors, not in git.

## Stop

Ask before publishing if geopolitics still names other groups on-screen, or if a judgment cut would remove the only setup for a later slide. Do not invent branding, doctrine, or strategy that was not in the recording.
