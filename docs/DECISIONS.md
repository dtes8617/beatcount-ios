# Decision Log

Chronological record of product and technical decisions, with rationale. `SPEC.md` and
`ARCHITECTURE.md` are the *current* canon; this file explains **why** and **when**.

## 2026-07-04 — Project inception & scope (owner-driven)

| # | Decision | Rationale / trigger |
| --- | --- | --- |
| 1 | Use case: **dance practice**, users in **Taiwan** | Owner statement |
| 2 | MVP = **synchronized in-app playback + big on-screen count display**; file export demoted to post-MVP | Owner: "Not really need to export an exact file, but if it can be proper display on the screen can be appreciated." Architecture keeps export ~100 lines away (offline render of the same graph) |
| 3 | Templates: 8-count **and sub-beat "&" counts** (`1 & 2 &`) | Owner: needed for faster rhythms / precise choreography. "&" = beat midpoints (straight-eighths assumption documented; swing detection deferred) |
| 4 | **Pitch-preserving speed control** 0.5–1.25× | Owner: "a speed option can be helpful" — core drill workflow |
| 5 | **Local project library with cached analysis** | Owner: analysis can be long; same music must reopen instantly. Analyze once per track |
| 6 | Input: **audio + video files** (video → extract audio track, same pipeline) | Owner asked for both. Video import is also the sanctioned answer to the YouTube use case |
| 7 | **No YouTube (or streaming) download — permanent non-goal** | YouTube ToS violation + App Store Review Guideline 5.2.3 rejection + extractor fragility. Decided after owner asked; owner accepted the video-import mitigation |
| 8 | **UI in Traditional Chinese (zh-TW)**; English stays the development language via one String Catalog | Owner: users are in Taiwan. Reviewed zh-TW copy lives in the design mockup |

## 2026-07-04 — Design (3 candidates, 3-judge panel; winner: "mvp-minimal", 2/3 votes)

Two screens (資料庫 Library / 播放器 Player) + 校正節拍 Fix Beats sheet + 全螢幕數拍 Big Count overlay.
Grafts merged from the losing candidates: Counts A/B switch, single-step Undo, Shift-the-"1" steppers,
phrase-boundary template switching, scrub-snap-to-"1", duplicate-import hash detection, missing-audio
hash-relink recovery, low-confidence soft caption (no forced verification gate), two-step manual tap
fallback, Big Count overlay for across-the-room readability.

## 2026-07-04 — Technical (research-verified)

| # | Decision | Rationale |
| --- | --- | --- |
| 9 | Beat detection: **custom Swift DSP on Accelerate/vDSP** (spectral flux → autocorrelation w/ log-Gaussian prior + octave-candidate scoring → Ellis-2007 DP tracking) behind a `BeatAnalyzer` protocol | Every off-the-shelf library is license-disqualified for App Store (aubio GPL-3, Essentia AGPL-3, madmom models CC BY-NC-SA, Superpowered paid). Steady-tempo dance music is the classic algorithm's easy case |
| 10 | Upgrade paths: Apple **Music Understanding** framework (`MusicUnderstandingSession`, iOS 27, WWDC26 — verified to exist) as preferred engine when available (bars ⇒ automatic downbeat); MIT-licensed **Beat This!** via CoreML if DSP underperforms | Both slot behind `BeatAnalyzer`; `analyzerId+version` stored per analysis |
| 11 | Playback: single AVAudioEngine, **dual-path graph** — music → `AVAudioUnitTimePitch` → mixer; voice → voice-mixer → mixer (voice bypasses the stretcher) | Counts stay crisp at 0.5×; only their schedule times scale by 1/rate. Full pre-schedule via `scheduleBuffer(_:at:)` from a common `play(at:)` anchor; one `rebuildPlayback()` path for every disruption |
| 12 | Display sync driven from the **audio clock** (`playerTime(forNodeTime:)` − `outputLatency`) via `TimelineView(.animation)` — never wall-clock timers | Sync is the product: ±30 ms at every speed is a release gate |
| 13 | Persistence: **folder-per-project + Codable JSON sidecars** (`project.json`, `beats.json`, `waveform.bin`); SwiftData rejected for MVP | Bulk numeric arrays + one settings struct don't earn a database; sidecars are debuggable and format-portable |
| 14 | Voice assets: self-record one voice (11 clips: 1–8, "and", accented 1/5) as 48 kHz mono CAF with per-clip `pCenterMs` manifest; ElevenLabs paid tier as fallback; TTS files as dev placeholders only | Zero licensing ambiguity; manifest makes voices/locales pure content drops |
| 15 | Corrections are **non-destructive transforms** over the immutable raw beat list (`tempoMultiplier`, `phaseOffsetMs`, `downbeatAnchorIndex`, `manualBeats?`) | Undo/Reset are free; a future export replays the same transforms |

## 2026-07-04 — Publishing

- Repo made **public** (owner approved) to serve the mockup via GitHub Pages:
  https://dtes8617.github.io/beatcount-ios/ (`index.html` generated from `design/mockup.html`
  by `tools/build_pages.py`).
- Leftover `dtes8617/beatcount-mockup` mirror repo is redundant — owner may delete it
  (requires `delete_repo` scope or the web UI).
- Mockup demo voice: browser-TTS, **on by default**, unlocked inside a tap gesture (iOS Safari
  requirement); iPhone ring/silent switch mutes web TTS — real app is immune (AVAudioSession `.playback`).

## Open questions (owner-level; none block development)

1. **Count-voice language**: English ("five six seven eight" — common in Taiwan studios) or Mandarin
   (一…八)? Working default: English. Manifest supports both as content drops.
2. **Whose voice** records the counts (self/friend vs ~$5 ElevenLabs Starter fallback)?
3. **App Store intent**: real goal (affects voice-asset provenance bookkeeping + $99/yr) or
   personal/TestFlight-only?
4. Keep **1.25×** speed or cap at 1×? (Kept for now; dropping relaxes voice-clip length budgets.)
5. Final **app name** — "BeatCount" is a working title (「數拍」 floated as a zh option).
6. **Storage tolerance**: each project keeps a full audio copy (a few MB/song) — fine at expected
   library size?
