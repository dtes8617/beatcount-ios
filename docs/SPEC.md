# BeatCount — Product Specification (MVP)

## Vision

BeatCount turns any song into a dance-practice track: import a music or video file, the app finds the beats on-device, and then plays the music with a real human voice counting dance 8-counts ("one, two, … eight") perfectly locked to the beat, while a giant on-screen count — readable from across the room on a propped-up phone — tracks every beat and phrase. Dancers drill at reduced, pitch-preserved speed, jump back to the top of the current 8-count, and fix any beat-detection mistake by ear in seconds while the music keeps playing. Every track is a persistent local project: analysis runs once, corrections and settings stick, and every later session is open-app → tap Play → dance.

---

## MVP Scope

| Area | In MVP | Notes |
|---|---|---|
| Input | Audio files (MP3, M4A/AAC, WAV) **and video files** (MP4/MOV — audio track is extracted) via the Files picker | Video import shows an "Extracting audio…" step, then joins the identical pipeline |
| Beat analysis | Automatic on-device tempo + beat detection, cached per project, runs once per track | No server, no network |
| Playback | Music + pre-recorded human voice counts, sample-locked, in-app | Screen stays awake during playback |
| Count display | Giant current-count numeral, 8-dot phrase indicator, waveform with beat ticks + playhead; full-screen **Big Count** overlay for distance/landscape | Readable at 3–4 m |
| Templates | Two: **1–8** (plain 8-count) and **1 & 2 &** (with sub-beat "&" counts halfway between beats) | Switch applies at the next phrase boundary ("1") |
| Speed | Pitch-preserving 0.5× / 0.75× / 0.9× / 1× / 1.25×; counts stay locked at every speed | Persists per project |
| Corrections | Halve/double tempo, ±10 ms phase nudge, downbeat rotation (steppers + tap-on-1), manual tap-tempo fallback, Counts On/Off A/B, single-step Undo, Reset to Detected | Live over playback; persist per project |
| Persistence | Local project library: copied audio, cached analysis, all settings & corrections; auto-save everywhere (no Save button) | Cold launch resumes the last-opened project |
| Voice | ONE human voice: "one"…"eight" + short "and" | Count language (English vs Mandarin 一…八) is an owner decision; English is the working default — common in Taiwan dance studios |
| Localization | UI ships in **Traditional Chinese (zh-TW)** — target users are dancers in Taiwan | UI copy in this spec is the English design source; every string ships through a String Catalog with a complete zh-TW translation (see mockup for the zh-TW copy) |

### Non-goals (explicit)

- **No YouTube (or any streaming-service) download/rip — in any version.** It violates YouTube's Terms of Service and Apple rejects such apps (App Store Review Guideline 5.2.3). The sanctioned path for "the song is on YouTube" is: save the video file to the device, then import it — BeatCount extracts the audio.
- **No audio export of the mix in MVP.** Exporting music+counts to a file is a stretch goal / post-MVP; the architecture keeps it cheap to add (see ARCHITECTURE.md appendix).
- No mic recording, no multiple voices, no additional count templates, no per-section/tempo-drift grid editing, no cloud sync, no background-audio entitlement, no search/sort/tags in the library, no Apple Music (DRM) content.

---

## Design Overview

Two screens, one sheet, one overlay:

1. **Library** — the project list; a launcher, not a destination.
2. **Player** — the app. Count display, transport, speed, template, voice mix.
3. **Fix Beats** (bottom sheet over the Player) — verify and correct the beat grid over live playback.
4. **Big Count** (full-screen overlay on the Player) — maximum-size count for across-the-room practice, portrait and landscape.

Cold launch resumes directly into the last-opened project's Player (back chevron returns to Library). If the last project can't be restored, the app falls back to Library gracefully.

---

## Screen: Library

**Purpose.** Pick a project or import a new track. Exists because projects persist; optimized for getting out of the way.

### Elements

- Large-title nav bar **"BeatCount"** with a **"+"** toolbar button (accessibility label: "Import Music or Video").
- Project rows, sorted by last-opened: song title; secondary line `126 BPM · 3:42 · 0.75×` (detected/corrected tempo, duration, saved speed — speed shown only when ≠ 1×); small waveform thumbnail.
- Row still analyzing: inline circular progress ring in place of the BPM — `Finding beats… 40%`. Tapping opens the Player anyway.
- Row still extracting from video: `Extracting audio…` with an indeterminate spinner, then transitions to the analyzing state.
- Swipe-to-delete with confirmation: **"Delete “Song Name”?"** / "This removes the copied audio and its beat analysis." — buttons **Delete** (destructive) / **Cancel**.
- Context menu on row: **Rename**, **Re-analyze** (confirms: "This replaces the beat grid and your corrections. Re-analyze?"), **Delete**.
- Tapping **+** presents the system Files document picker accepting **audio (mp3, m4a/aac, wav) and video (mp4, mov)** types. On pick: the file is copied into the sandbox (video: audio track extracted first), a project is created named after the file, analysis starts in the background, and the app pushes **straight into the Player** — no naming step, no progress modal.

### States

- **Empty (first launch):** centered placeholder — music-note icon, **"No songs yet"**, "Import a song or video and BeatCount will find the beats and count you in.", prominent button **"Import Music or Video"**. Footnote: *"BeatCount can't download from YouTube or streaming apps. Save the audio or video file to your device first, then import it here."*
- **Duplicate import** (same content hash): alert **"Already in your library"** with **Open Existing** / **Import Copy**.
- **Import errors** (alerts, specific copy):
  - DRM-protected: "This file is copy-protected and can't be decoded. Apple Music downloads won't work — use a DRM-free file."
  - Undecodable: "Couldn't read this audio file."
  - Video with no audio track: "This video has no audio track."
  - Video extraction failed: "Couldn't extract the audio from this video."
  - iCloud not downloaded: row shows "Downloading from iCloud…" spinner, cancellable; import continues automatically.
  - Low storage: "Not enough space to copy this song."
- **Analysis failed row:** warning badge, subtitle "Beat detection failed — tap to retry or set beats by tapping". Tapping opens the Player with the Fix Beats sheet pre-opened in manual tap-tempo mode.
- **Missing audio (restore recovery):** if a project's sandboxed audio is gone (e.g. after a device restore), the row shows "Audio file missing — tap to re-import". Tapping opens the Files picker; if the picked file's content hash matches, the app **relinks it and reuses the cached beat analysis and corrections** — no re-analysis, no lost work. If the hash differs: alert "This looks like a different file. Import it as a new song?" **Import as New** / **Cancel**.

---

## Screen: Player

**Purpose.** Practice happens here: giant count, synchronized voice, transport, speed, template. Hosts the Fix Beats sheet and the Big Count overlay.

### Elements

- **Top bar:** back chevron **"Library"** · song title (truncates; tap to rename) · **"Fix Beats"** button (tuning-fork icon + label) · expand icon (**"Big Count"**, accessibility label "Full-Screen Count").
- **Count display** (top ~55% of screen): current count as a single numeral at maximum size (rounded, monospaced-digit font, ~40% of screen height, high contrast). Count **"1" is tinted the accent color** to mark the phrase start. With the "&" template active, a half-size **"&"** flashes between numerals. Below: a row of **8 dots** (current count filled; dot 1 slightly larger) showing phrase position. Screen sleep is disabled while playing.
- **Waveform strip** (~12% height): rendered waveform with beat ticks — downbeats ("1") taller and accent-colored, other beats thin — plus playhead. Drag to scrub; **the resume point snaps to the nearest count 1**, so every restart is phrase-aligned. Voice counts resume in sync immediately.
- **Transport row:** **"↺ 8"** button (jump to the start of the current 8-count — the drill-this-phrase button) · giant **Play/Pause** (≥ 88 pt hit target) · elapsed/total time.
- **Speed:** segmented control **`0.5× · 0.75× · 0.9× · 1× · 1.25×`** — pitch-preserving; voice counts stay sample-locked at any rate; selection persists per project instantly. Haptic tick on change.
- **Counts (template):** segmented control **`1–8`** | **`1 & 2 &`**. Switching takes effect **at the next phrase boundary** (the next "1") so counting never stutters mid-bar; persists per project.
- **Voice slider:** speaker icon + slider for count-voice gain relative to the music (music never ducks); persists per project.
- All state (speed, template, voice gain, corrections, playback position) auto-saves continuously. **There is no Save button anywhere in the app.**

### States

- **Extracting (video import):** count area shows "Extracting audio…" with a spinner, then hands off to Analyzing.
- **Analyzing (fresh import):** count area shows a determinate ring, **"Finding beats…"** with percent. The waveform draws as soon as decode finishes. Play is enabled for music-only preview with the caption *"Counts start when analysis finishes."* On completion: single haptic tick, Player animates to ready.
- **Ready/idle:** dimmed "1" in the count display, dots empty, Play prominent. **Low-confidence nudge:** if the analyzer's confidence is low or beat-interval variance is high, a one-time amber caption appears: *"Detection wasn't confident — listen closely, and tap Fix Beats if it's off."*
- **Playing:** as designed. Controls other than the transport dim to 40% opacity after 4 s without touch and restore on any tap; the count display and dots never dim.
- **Analysis failed:** count area shows **"Couldn't find the beats"** with buttons **"Try Again"** and **"Tap Beats Myself"** (opens Fix Beats in manual mode).
- **End of song:** playback stops; playhead returns to 0 (no auto-loop in MVP).
- **Interruption** (call/Siri): pauses cleanly, stays paused. **Route change** (headphones disconnect): pauses per HIG.

---

## Overlay: Big Count

**Purpose.** Distance-readable full-screen count for a phone propped across the room. A thin presentation layer over the Player's existing playback state — not a separate screen or state machine.

### Elements

- Full-screen count digit at ~70% of the shorter screen dimension, maximum contrast (white on black in dark mode); subtle pulse on each beat; accent flash ring on count "1"; "&" as a half-size glyph.
- Phrase dots (1–8) along the bottom edge, thick enough to read at 4 m; thin song-progress bar beneath; current speed badge (e.g. "0.75×") at caption size in a corner.
- **Portrait and landscape** (landscape maximizes digit width for a sideways-propped phone).
- Single tap anywhere summons an oversized control overlay — **Pause/Play** (center, ~120 pt), **↺ 8** left, speed chips right, **"Exit"** top-left — auto-hides after 4 s. Two-finger double-tap always exits, as an escape hatch.
- Screen keep-awake stays on in this mode even while paused.

### States

- **Playing / paused** (paused: digit at 40% opacity with "Paused" caption; controls stay visible).
- **End of track:** digit shows "—", controls auto-reveal.

---

## Sheet: Fix Beats (over the Player)

**Purpose.** Verify and correct the detected grid without stopping the music. Playback continues under the sheet; every control gives audible feedback within one beat. Verification IS playback — the overlaid voice against the music is the most sensitive detector of grid errors.

### Elements

- **Medium-detent sheet.** The Player's count display remains visible above it and keeps counting.
- **Header:** live readout **"Detected: 126.4 BPM"** (shows corrected value when corrections exist, e.g. "126.4 → 63.2 BPM · +30 ms"); **"Undo"** button (single-step: reverts the last correction; shake-to-undo also works); **"Reset to Detected"** text button.
- **COUNTS A/B switch:** labeled **"Counts"**, On/Off — instantly mutes/unmutes the voice bus for an A/B of the counts against the raw music. The fastest ear-test of a suspect grid.
- **TEMPO row:** buttons **"½× → 63"** and **"2× → 253"** (labels show the resulting BPM; disabled with caption *"Out of range"* if the result would leave 40–220 BPM). Caption: *"Counts feel twice too fast? Halve. Half as fast? Double."* Applies on the next beat.
- **SHIFT row:** buttons **"−10 ms"** / **"+10 ms"** — press-and-hold auto-repeats with one haptic per step; live cumulative readout (e.g. **"+30 ms"**). Caption: *"Counts early or late? Nudge until the voice lands on the beat."*
- **THE "1" row:** steppers **"Shift 1 ◀"** / **"Shift 1 ▶"** — rotate which beat is counted as "1" by exactly one beat per tap, deterministic and immune to touch/audio latency — next to the **TAP ON 1 pad** (below).
- **TAP pad:** full-width pad labeled **"TAP ON 1"** with caption *"Tap this on every count 1 you hear."* One tap rotates the phrase so the nearest beat becomes count 1. Three or more rhythmic taps additionally re-fit the grid phase to the taps' mean offset, compensated for measured audio-output latency plus a calibrated touch-latency constant. (Full tempo re-estimation is **not** on this pad — it lives only in the explicit manual mode below, so the pad stays predictable.)
- **Bluetooth caption:** when the active output route is Bluetooth, a caption appears: *"Wireless audio adds delay — for precise timing fixes, use the speaker or wired headphones."*
- **"Done"** (top-right) dismisses. Corrections were already applied and persisted live — Done is dismissal, not confirmation.

### States

- **Default:** opens with playback running (auto-starts play from the current position if paused) so verification begins immediately.
- **Manual mode** (detection failed, or chosen from the failed state): a two-step flow replaces the correction rows. **Step 1 — "Tap the tempo":** big pad, *"Tap along with the beat — keep tapping until the number settles"*, live-settling BPM readout and a `Keep tapping… 5/8` counter. **Step 2 — "Tap the 1":** one tap on a downbeat. Then the normal correction rows appear for nudge/verify.
- **Tempo-drift warning:** if detected beat intervals vary > 4%, caption: *"This song's tempo drifts — counts may wander in places."*
- **Reset confirmation** (only if corrections exist): "Discard your corrections and restore the detected beats?" **Reset** / **Cancel**.

---

## Primary Flow

1. **Cold launch, first run:** Library empty state. One button: **Import Music or Video**.
2. Tap it → system Files picker. User picks an MP3 (or an MP4 dance video).
3. The file is copied into the sandbox as a new project (video: "Extracting audio…" runs first, typically a few seconds) and beat analysis starts in the background. The app pushes **straight into the Player**: "Finding beats… 40%". Two taps so far.
4. Analysis completes (typically well under ~15 s for a 4-minute song) — haptic tick; Player flips to ready: beat-ticked waveform, dimmed "1", BPM known. If confidence was low, the amber "listen closely" caption shows once.
5. Tap **Play**. Music plays; the human voice counts "one, two, … eight" locked to each beat; the giant numeral flips per beat; the 8 dots track the phrase; the playhead moves. Screen stays awake. Prop the phone (tap **Big Count** for full-screen/landscape) and dance.
6. If the counts feel wrong: tap **Fix Beats**, correct while the music keeps playing (median fix is one button press), tap **Done**.
7. To drill: tap **0.75×** — music slows, pitch unchanged, counts stay locked. Tap **↺ 8** to repeat the current phrase. Scrub the waveform — it snaps to the nearest "1".
8. Lock the phone and leave. Everything is already saved.
9. **Every later session:** cold launch resumes directly into that Player. Analysis is cached. Open app → tap Play → dancing. Two taps, zero waits.

---

## Correction UX (bad beat detection)

The three known failure modes map to dedicated, labeled, one-gesture controls, applied live over continuing playback and persisted as reversible transforms on the cached beat list (the raw analysis is never overwritten):

1. **Tempo octave error** (counts twice too fast / half as fast — unmistakable to a dancer within two counts): tap **½×** or **2×**. Labels show the resulting BPM before you tap; halving drops alternate beats, doubling interpolates midpoints; audible on the next beat.
2. **Phase offset** (every count lands early/late by a constant amount): hold **−10 ms / +10 ms** until the voice sits on the beat (haptic per step, live cumulative readout) — or tap **TAP ON 1** in rhythm three-plus times to re-fit phase to your taps, latency-compensated. Use the **Counts** A/B switch to hear the raw track against your fix.
3. **Wrong downbeat** ("1" is on the wrong beat): tap **Shift 1 ◀/▶** to rotate deterministically, or tap **TAP ON 1** once at the true "1" — the nearest beat becomes count 1; nothing else moves.
4. **Total detection failure:** the two-step manual fallback — tap the tempo until the BPM settles, then tap the "1" — after which the normal audition/nudge tools apply.

Safety net: **Undo** reverts the last correction (a fumbled 2× tap never destroys a good intermediate state); **Reset to Detected** restores the raw analysis. All corrections persist with the project and survive re-opens; **Re-analyze** is the only thing that discards them, and it says so.

---

## Edge Cases & Error States (consolidated)

| Case | Behavior |
|---|---|
| DRM-protected file (.m4p / Apple Music) | Import fails with specific copy distinguishing "protected" from "corrupt" |
| Video without audio track / extraction failure | Specific alerts; no half-imported project left behind |
| iCloud file not local | Auto-download with visible progress; cancellable |
| Disk full during copy | Alert; partial files cleaned up |
| Duplicate import (hash match) | "Already in your library" → Open Existing / Import Copy |
| Analysis failure (silence, speech, noise) | Failed state → Try Again / Tap Beats Myself (manual mode) |
| Tempo-drifting song (live/rubato) | Warning caption; global corrections still apply; per-section editing is out of scope |
| Missing audio after restore | Re-import + hash relink reuses cached analysis and corrections |
| Interruption (call/Siri) | Pause; stay paused |
| Route change (headphones out) | Pause; re-read output latency for display/tap compensation |
| Bluetooth output | Caption in Fix Beats warning about wireless delay |
| Last-opened project unrestorable at cold launch | Graceful fallback to Library |
| Very long file (> 15 min) | Allowed; analysis caption "Long track — analysis may take a minute" |
| End of track | Stop, reset playhead; no auto-loop |

---

## Success Criteria (MVP is done when…)

1. **Sync:** with speaker or wired output, voice-count onsets land within **±30 ms** of beat times at every speed (0.5×–1.25×), verified by recording device output and measuring; no audible drift over a full 4-minute song. The on-screen numeral flip matches the heard count.
2. **Detection:** on a 10-track personal test set of steady-tempo dance music, ≥ 8/10 tracks are correct (right octave, phase within ±50 ms, any downbeat) with **at most one** correction gesture; beat F-measure ≥ 0.9 (±70 ms) vs. the desktop reference oracle.
3. **Speed of loop:** returning session is open-app → Play in **2 taps**; a fresh import reaches counting playback in under ~30 s for a 4-minute MP3 on an iPhone 12-class device or newer.
4. **Correction:** each of the three failure modes is fixable in ≤ 10 seconds without stopping playback; corrections persist across app relaunches; Undo and Reset behave as specified.
5. **Persistence:** analysis runs exactly once per track; re-opening any project is instant (< 1 s to ready); speed/template/voice-mix/corrections/position all restore.
6. **Readability:** the current count is comfortably readable at 3 m on the Player and 4 m in Big Count, portrait and landscape; the screen never sleeps mid-song.
7. **Video import:** an MP4/MOV with an audio track imports, extracts, analyzes, and plays identically to an audio import.
8. **Robustness:** every error state in the table above shows its specified copy; nothing dead-ends without a next action.
