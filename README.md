# BeatCount

An iOS app for dance practice: import a song, let the app detect the beats, and practice
with a human voice counting **"1 2 3 4 5 6 7 8"** (and **"&"** sub-beats) in perfect sync —
with a large on-screen count display you can read from across the room.

> **Status:** spec & design phase — no code yet.
>
> **Target users:** dancers in Taiwan — the UI ships in Traditional Chinese (zh-TW).

## Core loop (MVP)

1. **Import** an audio file (MP3 / M4A / WAV) — or a video file, whose audio track is
   extracted automatically — via the Files app.
2. The app **detects beats and tempo** on-device and caches the analysis — each track is
   analyzed once and stored as a project that reopens instantly.
3. **Verify & correct** the detected grid: nudge the offset, halve/double the BPM,
   tap where the "1" lands.
4. **Practice**: synchronized playback of music + voice counts, a big real-time count
   display, and pitch-preserving speed control (slow it down to drill).

Exporting the mix as a single audio file is a post-MVP stretch goal.

## Documentation

| Doc | Contents |
| --- | --- |
| [`docs/SPEC.md`](docs/SPEC.md) | Product spec: scope, screens, flows, edge cases |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Technical design: beat detection, audio pipeline, persistence |
| [`design/mockup.html`](design/mockup.html) | Clickable HTML mockup of every screen |

## Tech (planned)

- SwiftUI, iOS 17+
- AVFoundation / AVAudioEngine for playback and mixing
- On-device beat detection (see `docs/ARCHITECTURE.md` for the chosen approach)
- No server — everything runs and persists locally
