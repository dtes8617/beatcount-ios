# CLAUDE.md — project brief

Read this first when picking up work in this repo.

## What this is

**BeatCount** (working title) — a personal iOS app for **dance practice**, target users in **Taiwan**.
Core loop: import a song (audio file, or video → audio extracted) → on-device beat detection (cached
per project) → synchronized playback with a **human voice counting dance 8-counts** (「1 2 3 4 5 6 7 8」,
optional "&" sub-beats) plus a **giant on-screen count** readable from across the room → pitch-preserving
speed control for drilling. Owner: Jude (GitHub `dtes8617`).

## Status (last updated 2026-07-04)

**Spec & design phase complete. No Swift code exists yet.**
Agreed next step: scaffold the Xcode project and build `BeatKit` (beat detection) first, validated
against known-BPM fixtures and the desktop librosa oracle before any UI work.

## Canonical documents (in order of authority)

| Doc | Role |
| --- | --- |
| `docs/SPEC.md` | Product spec — scope table, all screens/states with exact copy, correction UX, success criteria. **Scope disputes resolve here.** |
| `docs/ARCHITECTURE.md` | Technical plan — beat-detection algorithm, AVAudioEngine graph, persistence, voice-asset spec, testing strategy. |
| `docs/DECISIONS.md` | Decision log with rationale + dates, and the open questions only the owner can answer. |
| `design/mockup.html` | Clickable mockup **source** (see publishing workflow below). |

## Hard product invariants — don't re-litigate without the owner

- MVP deliverable is **in-app synchronized playback + on-screen count display**. File export is
  post-MVP (owner explicitly deprioritized it). The engine design keeps it ~100 lines away.
- Templates: `1–8` and `1 & 2 &` (sub-beat "&" = beat midpoints). Speed: 0.5–1.25×, pitch-preserving,
  counts stay beat-locked at every rate.
- Local project library: analyze once per track, cache analysis + corrections + settings; cold launch
  resumes the last project.
- Input: audio (MP3/M4A/WAV) **and** video (MP4/MOV, extract audio). **Direct YouTube download is a
  permanent non-goal** (YouTube ToS + App Store Guideline 5.2.3) — the owner asked twice; the answer
  stays no. Video-file import is the sanctioned mitigation.
- **UI ships in Traditional Chinese (zh-TW)**; development language (code, string keys, docs) is
  English via one String Catalog. The reviewed zh-TW copy lives in the mockup.
- No GPL/AGPL dependencies ever (App Store possibility); current plan is zero third-party runtime deps.
- Beat detection is expected to be wrong sometimes — the correction UX (½×/2×, ±10 ms nudge,
  rotate-the-"1", tap fallback) is core product, not an afterthought.

## Mockup publishing workflow

Two published copies, one source:

- `design/mockup.html` — the **source**. Deliberately has **no** `<!DOCTYPE>/<html>/<head>` wrapper
  (Claude-artifact format; the artifact publisher adds the skeleton).
- `index.html` — **generated** for GitHub Pages. Never edit by hand; regenerate after any mockup change:
  `python3 tools/build_pages.py`
- Public link (share with anyone): **https://dtes8617.github.io/beatcount-ios/**
  (Pages: main branch, root, `.nojekyll`; the CDN caches ~10 min — hard-refresh after deploys.)
- Claude artifact (workspace-only, for design sessions):
  https://claude.ai/code/artifact/5c018d62-c931-4521-9341-35c46699597b — republish from
  `design/mockup.html`, keep the 💃 favicon and stable title.

Mockup demo-voice quirks (already handled in code — don't regress): iOS Safari requires
`speechSynthesis.speak()` inside a tap gesture (unlock happens on the voice toggle and the first
play tap); never `cancel()` before each utterance (wedges iOS queue — drop the count instead);
the iPhone ring/silent switch mutes web TTS entirely (the real app uses AVAudioSession `.playback`
and is immune).

## Git / GitHub conventions

- Personal repo of `dtes8617` — the Taboola/Bitbucket conventions from the user-level CLAUDE.md
  do **not** apply here. Use `gh`, not `bkt`.
- Repo-local identity is set: `Jude <dtes8617@users.noreply.github.com>` — keep it; don't commit
  with the work email.
- Repo is **public** (owner approved 2026-07-04) and serves GitHub Pages from main/root.
- Commit style: imperative subject, body explains why; Co-Authored-By Claude trailer.

## Next steps (agreed order)

1. Xcode project scaffold: iOS 17+, SwiftUI, module layout per `ARCHITECTURE.md` §7, no packages.
2. `tools/analysis-oracle/`: Python venv (librosa) + fixture set (click tracks 60–174 BPM, offsets,
   swing, noise) exporting JSON beat lists for Swift tests.
3. `BeatKit`: spectral-flux → autocorrelation (log-Gaussian prior, octave scoring) → Ellis-2007 DP
   tracker behind the `BeatAnalyzer` protocol; hit F ≥ 0.9 (±70 ms) on fixtures before moving on.
4. `PlaybackKit` (dual-path AVAudioEngine graph) → then UI screens against the mockup.
5. Voice assets last (dev placeholder: pre-rendered TTS files under the same manifest scheme).

## Open questions for the owner

See the current list at the bottom of `docs/DECISIONS.md` (count-voice language, whose voice,
App Store intent, 1.25× keep/drop, final app name).
