# BeatCount — Technical Architecture (MVP)

iOS 17+, SwiftUI, 100% on-device, zero third-party runtime dependencies (all Apple frameworks) — so zero licensing risk for a future App Store release.

---

## 1. Module Breakdown

Single app target, organized as feature-oriented Swift packages/folders behind small protocols:

| Module | Responsibility | Key types |
|---|---|---|
| `ImportKit` | File picking, security-scoped copy, **video audio-extraction**, hashing, dedupe, project creation | `Importer`, `VideoAudioExtractor`, `ContentHasher` |
| `BeatKit` | Beat/tempo analysis + correction transforms + count-timeline derivation | `BeatAnalyzer` (protocol), `AccelerateBeatAnalyzer`, `BeatGrid`, `Corrections`, `CountTimeline` |
| `PlaybackKit` | AVAudioEngine graph, count scheduling, speed, seek, session/lifecycle | `PlaybackEngine`, `CountScheduler`, `PlaybackAnchor` |
| `VoiceKit` | Voice-asset loading, manifest, p-center compensation | `VoiceBank`, `VoiceManifest` |
| `ProjectStore` | Folder-per-project persistence, library index, migration by `schemaVersion` | `Project`, `ProjectStore` |
| `UI` | SwiftUI screens: Library, Player, Fix Beats sheet, Big Count overlay; waveform `Canvas` rendering | `LibraryView`, `PlayerView`, `FixBeatsSheet`, `BigCountOverlay`, `WaveformView` |

Dependency direction: `UI → PlaybackKit/ProjectStore → BeatKit/VoiceKit/ImportKit`. `BeatKit` and `VoiceKit` have no UI or engine imports (pure + testable).

---

## 2. Beat Detection

### Decision

**Custom Swift analyzer on Accelerate/vDSP** (spectral-flux onset envelope → autocorrelation tempo with log-Gaussian prior → Ellis-2007 dynamic-programming beat tracking), behind a `BeatAnalyzer` protocol. Rationale: every off-the-shelf option is license-disqualified for App Store distribution (aubio GPL-3, Essentia AGPL-3, madmom models CC BY-NC-SA, Superpowered paid-only), and steady-tempo dance music is the easy case for this classic algorithm (~85–95% beat F-measure expected). The product's correction UX covers exactly this algorithm's failure modes.

```swift
protocol BeatAnalyzer {
    func analyze(url: URL, progress: @escaping (Double) -> Void) async throws -> BeatAnalysis
}
```

Future engines slot in behind the protocol: Apple's **Music Understanding** framework (`MusicUnderstandingSession`, iOS 27) becomes the preferred engine on iOS 27+ — `analyze(for: [.rhythm])` returns `RhythmResult.beats`/`.bars`/`.beatsPerMinute`, and bars pre-fill the downbeat "1". The MIT-licensed **Beat This!** model (CoreML-converted, 8.1 MB small variant) is the cross-version quality upgrade if the DSP underperforms. `analyzerId + version` is stored with each analysis so engine upgrades can offer optional re-analysis.

### Algorithm outline (`AccelerateBeatAnalyzer`)

1. **Decode:** `AVAudioFile` → chunked reads (65,536 frames) → `AVAudioConverter` downmix to mono Float32 @ 22,050 Hz. Never whole-file in memory.
2. **Onset envelope:** STFT window 1024 / hop 512 (~43 fps) via `vDSP.FFT`; magnitude → log-compress `log(1 + 100·|X|)` → half-wave-rectified first difference summed over bins = spectral flux; subtract local mean (~0.4 s window), clamp at 0.
3. **Tempo:** autocorrelation of the envelope (`vDSP_conv`) over lags for 60–200 BPM, weighted by a log-Gaussian prior centered ~120 BPM (σ ≈ 1 octave). Explicitly score `{τ/2, τ, 2τ}` candidates against prior + comb energy to reduce octave errors. **Confidence** = autocorrelation peak prominence (0–1), stored with the result and used for the Player's "detection wasn't confident" caption; beat-interval variance > 4% triggers the tempo-drift caption.
4. **Beat tracking:** Ellis-2007 DP — `C(t) = O(t) + max_τ' [C(τ') − α·(log(Δ/period))²]`, tightness α ≈ 100 (librosa's parameterization), backtrace from the best final beat.
5. **Outputs:** raw beat list `[Double]` (seconds), global BPM, confidence, onset envelope downsampled to ~50 Hz (for the beat-grid UI), waveform overview (~4,000 min/max pairs for the scrubber). Analysis of a 3–4 min track: ~1–3 s on modern iPhones; runs on a background task, progress reported to the UI.

### Corrections layer (never mutates raw beats)

```swift
struct Corrections: Codable {
    var tempoMultiplier: Double = 1      // 0.5 | 1 | 2 (halve = drop alternate beats; double = interpolate midpoints)
    var phaseOffsetMs: Double = 0        // additive to all beat times
    var downbeatAnchorIndex: Int = 0     // count of beat i = ((i − anchor) mod 8) + 1
    var manualBeats: [Double]? = nil     // full replacement grid from tap-tempo fallback
}
```

The Fix Beats sheet's **Undo** keeps the previous `Corrections` value (single-step history); **Reset to Detected** restores `Corrections()`. Because raw analysis is immutable, both are free, and a future export replays the same transforms.

### Sub-beat "&" grid derivation

Derived at **timeline-build time**, never at analysis time: `and[i] = (beat[i] + beat[i+1]) / 2` (true midpoint — robust to jitter and mild drift because it always lands inside the actual interval), with the final "&" extrapolated using the last inter-beat interval. Known limitation: swing/shuffle puts the real "&" at ~2/3 of the interval, not 1/2 — the "&" template assumes straight eighths (documented; post-MVP: detect swing by comparing onset energy at the 1/2 vs 2/3 positions and offer a swing ratio).

The derived count-event timeline `[(musicTime: Double, token: CountToken)]` is **never cached** — it recomputes from `beats + Corrections + template` in < 1 ms.

### Failure modes → mitigations

| Failure | Cause | Mitigation |
|---|---|---|
| Tempo octave (2×/0.5×) | Half/double-time feel | `{τ/2, τ, 2τ}` scoring + prior; **½×/2× buttons** with predicted-BPM labels |
| Phase offset (10–30 ms typical) | Envelope smoothing bias | ±10 ms nudge with live readout; tap-based phase re-fit (latency-compensated) |
| Downbeat ambiguity | Algorithm doesn't detect downbeats | User anchors "1" (steppers or tap); iOS 27 Music Understanding pre-fills it later |
| Tempo drift / rubato | Constant-grid assumption | Drift caption; out of scope for grid editing (documented) |
| Total failure (speech, noise) | No periodic energy | Two-step manual fallback: tap tempo (8+ taps, settling BPM) then tap "1" → `manualBeats` |
| Tap corruption over Bluetooth | 100–300 ms under-reported output latency | Compensate with `AVAudioSession.outputLatency` + calibrated touch constant; Bluetooth warning caption; per-route offsets deferred post-MVP |

---

## 3. Import Pipeline

1. **Pick:** SwiftUI `.fileImporter(allowedContentTypes: [.mp3, .mpeg4Audio, .wav, .aiff, .movie, .mpeg4Movie, .quickTimeMovie], allowsMultipleSelection: false)`.
2. **Access & copy:** `url.startAccessingSecurityScopedResource()` (deferred stop); `NSFileCoordinator` coordinated read (forces iCloud Drive download, with visible progress); `FileManager` copy into the new project folder. Failures clean up the partial folder atomically.
3. **Video branch (MVP — late scope addition):** if the UTType conforms to `.movie`, extract the audio track before analysis: `AVAssetExportSession(asset: AVURLAsset(url:), presetName: AVAssetExportPresetAppleM4A)` → `audio.m4a` in the project folder (UI state: "Extracting audio…"). If the preset is unavailable for the asset (unusual codecs), fall back to `AVAssetReader`/`AVAssetWriter` PCM→AAC passthrough. Assets with no audio track fail with the specific alert; the original video file is **not** kept. From here the project is indistinguishable from an audio import.
4. **Hash & dedupe:** SHA-256 of the (extracted) audio content via `CryptoKit`. Match against the library → "Already in your library" (Open Existing / Import Copy). The hash is also what **missing-audio recovery** uses: re-import, hash-match, relink, reuse cached analysis.
5. **Decode gate:** open the copy with `AVAudioFile` (decodes MP3/AAC/ALAC/WAV/AIFF/CAF via ExtAudioFile). FairPlay-DRM `.m4p` throws → the "copy-protected" alert. Open off the main thread (VBR MP3 packet-table scan).
6. **Kick off analysis** on a background task; navigate to the Player immediately.

---

## 4. Synchronized Playback Engine

### Graph (single `AVAudioEngine`)

```
musicPlayer (AVAudioPlayerNode, streams via scheduleSegment)
    → AVAudioUnitTimePitch (rate 0.5–1.25, pitch = 0 → pitch-preserving)
        → mainMixerNode
voicePlayer (AVAudioPlayerNode)
    → voiceMixer (AVAudioMixerNode — the voice-volume control, and the mute for the Counts A/B switch)
        → mainMixerNode
```

The voice path deliberately **bypasses the time-pitch unit**: count clips are never time-stretched (they stay crisp at 0.5×); only their *scheduled times* scale by `1/rate` — exact arithmetic. `AVAudioUnitVarispeed` is rejected (resampler; shifts pitch).

### Count scheduling (sample-accurate)

- Voice clips are preloaded once into ~11 shared `AVAudioPCMBuffer`s (see §6), pre-converted to the music file's sample rate at import of the voice bank to avoid connection-format mismatches.
- **Full pre-schedule strategy:** on (re)start, every remaining count event is enqueued via `voicePlayer.scheduleBuffer(_:at:)` with a sample-time-valid `AVAudioTime`. A 4-minute song with "&" counts is ~1,000 tiny enqueues of shared buffers — milliseconds of work.
- **Common anchor:** both players start from one future host time so their (zero-based-after-stop) sample timelines share an origin:
  `let anchor = AVAudioTime(hostTime: mach_absolute_time() + hostTicks(0.15))`; `musicPlayer.play(at: anchor)`; `voicePlayer.play(at: anchor)`.
- A count at music time `t`, with seek position `s`, rate `r`, voice sample rate `srV`:
  `voiceSampleTime = ((t − s) / r + timePitchLatency − pCenterSec(token)) × srV`
  where `timePitchLatency = timePitch.auAudioUnit.latency` (the music path carries the stretcher's algorithmic latency; the voice path doesn't — so counts are delayed by it), and `pCenterSec` aligns each word's *perceptual* onset (vowel), not its buffer start, to the beat (per-asset manifest value).
- **One code path for every disruption** — seek, pause-with-reschedule, rate change, template change, route/config change: read current music position → `stop()` both players (stop flushes queues and resets node timelines — a feature) → set `timePitch.rate` → `musicPlayer.scheduleSegment(file, startingFrame: seekFrame, …)` → recompute + re-enqueue remaining counts → `play(at:)` a fresh anchor. Never patch in-flight schedules with `.interrupts` (it also resets the node timeline mid-flight). Plain pause/resume uses `pause()` (no flush). Template switches are applied by scheduling the change to take effect **at the next phrase boundary** (next "1"): events before that boundary are kept, later events regenerated.
- Music streams from disk via `scheduleSegment` — the song is never loaded into one giant buffer; `seekFrame` is tracked by the engine so displayed position = `seekFrame/sr + playerTime.sampleTime/playerTime.sampleRate`.

### On-screen count display sync

- SwiftUI `TimelineView(.animation)` (per-frame, iOS 17+) computes the current music position each frame **from the audio clock, never wall time**: `musicPlayer.playerTime(forNodeTime: musicPlayer.lastRenderTime)` (guard nil — freeze display), extrapolated to "now" via host-time delta × rate, **minus `AVAudioSession.sharedInstance().outputLatency`** so the numeral matches what the ear hears (re-read on route change; accept imperfection on Bluetooth). Binary search over the count-event array yields the current count; the waveform + playhead render in `Canvas` inside the same `TimelineView`. The audio controller publishes only a small immutable `PlaybackAnchor` struct on start/seek/rate-change — position is never published at frame rate through `@Observable`.
- Because the time-pitch node pulls the music player at `rate × realtime`, `playerTime` advances in music-timeline samples regardless of speed — one clock drives both the display and the scheduler.

### Session & lifecycle

- `AVAudioSession.setCategory(.playback)` (plays under the silent switch; no background-audio entitlement in MVP), `setActive(true)` before `engine.start()`; `engine.prepare()` before any `play(at:)`.
- Observers: `AVAudioSession.interruptionNotification` (pause on `.began`; on `.ended` + `.shouldResume`, restart engine + full reschedule), `routeChangeNotification` (`.oldDeviceUnavailable` → pause; re-read `outputLatency`), `AVAudioEngineConfigurationChange` (engine self-stops on route/sample-rate change — rebuild connections and run the rebuild-playback path).
- All schedule math lives in one `rebuildPlayback(from position: Double, rate: Double)` function; every lifecycle event calls it. `UIApplication.isIdleTimerDisabled = true` while playing.

### Gotchas checklist (enforced by code review + tests)

`lastRenderTime` nil-guard everywhere · `AVAudioTime` must have `isSampleTimeValid` for node-relative scheduling · `scheduleBuffer` completion handlers run on an internal audio queue (hop off; prefer `.dataPlayedBack`) · `stop()` resets node time to 0 (always re-anchor) · connection-format vs buffer-format mismatch crashes (pre-convert voice assets) · open `AVAudioFile` off the main thread.

---

## 5. Persistence & Data Model

Folder-per-project + Codable JSON. **No SwiftData/Core Data** for MVP: the payload is one small settings struct plus bulk numeric arrays — no relations or queries that earn a database, and sidecar files are trivially debuggable and keep a future document/export format open.

```
Library/Application Support/Projects/<UUID>/
    audio.m4a | audio.mp3 | …     # verbatim audio copy, or the M4A extracted from video
    project.json                  # mutable user state
    beats.json                    # immutable analysis cache
    waveform.bin                  # 2,000–4,000 min/max envelope pairs (instant scrubber draw)
```

**`project.json`** — `{ schemaVersion, title, createdAt, lastOpenedAt, sourceFilename, sourceKind: "audio" | "video", audioSHA256, templateId: "eight" | "eightAnd", rate, musicVolume, countVolume, corrections { tempoMultiplier, phaseOffsetMs, downbeatAnchorIndex, manualBeats? }, playbackPositionSec }`

**`beats.json`** — `{ schemaVersion, analyzerId, analyzerVersion, audioSHA256, durationSec, sampleRate, bpmGlobal, confidence, beatIntervalVariance, beats: [Double], onsetEnvelope50Hz: [Float] }`

Notes: writes are atomic (`Data.write(.atomic)`) and auto-save on every change (no Save button). The library list is a directory scan (cheap at personal-library scale). `Application Support` is never purged by iOS; the **audio file only** gets `isExcludedFromBackup = true` (large, re-importable — and hash-relink recovery covers the restore case), while the small JSON/analysis stays in backup. The derived count timeline is never persisted. Last-opened project id lives in `UserDefaults` for cold-launch resume, with graceful fallback to Library if the folder fails validation.

---

## 6. Voice Assets

**Spec.** One voice; 11 shipped clips: `count_1 … count_8`, `count_and`, plus accented `count_1_accent`, `count_5_accent` (they open each half of the 8-count). Format: CAF / LPCM 16-bit / 48 kHz / mono (`afconvert -f caff -d LEI16@48000 -c 1`), < 1 MB total, zero decode cost into `AVAudioPCMBuffer`. Length budgets: numbers ≤ ~300 ms; "and" ≤ ~150 ms with a 10–20 ms fade-out (a half-beat at 140 BPM is ~214 ms; 1.25× packs un-stretched clips 20% closer). Per-clip processing: trim to ~10% of peak −5 ms, 5 ms fade-in, DC removal, high-pass 80–100 Hz, matched RMS ≈ −20 dBFS (accented variants +2–3 dB), true peak ≤ −3 dBFS.

**Manifest-driven bundle** (blue folder reference) so voices/locales are pure content drops:

```
Voices/en/instructor_f1/
    count_1.caf … count_and.caf
    voice.json   # { id, locale, assets: { "1": { file, pCenterMs, gainDb }, "and": {…}, … } }
```

`pCenterMs` — the measured offset from buffer start to the word's perceptual onset (vowel, e.g. the "ONE" in "w-ONE") — is subtracted at schedule time. This one number per asset is what makes counts feel locked.

**Sourcing plan.** Self-record in one session (48 kHz/24-bit WAV, fixed mic distance, to a ~100 BPM metronome in headphones, 3+ takes per word) → scripted sox/ffmpeg/afconvert cleanup (~one evening total). Zero licensing ambiguity — owned master, App Store safe. Fallback if the takes lack energy: **ElevenLabs Starter ($5, paid tier = commercial output rights** — subscribe *before* generating; archive invoices). Post-MVP extra voices: Fiverr with the perpetual "For Commercial Use" license. Dev placeholders: pre-rendered `AVSpeechSynthesizer.write(_:toBufferCallback:)` / macOS `say` output under `Voices/en/placeholder_tts/` with the identical structure — the real voice is a file swap; never synthesize live in the shipping app.

---

## 7. SwiftUI Project Structure

```
BeatCount/
    App/            BeatCountApp.swift (cold-launch resume), AppRouter
    UI/
        Library/    LibraryView, ProjectRow, ImportButton
        Player/     PlayerView, CountDisplayView, PhraseDotsView,
                    WaveformView (Canvas), TransportBar, SpeedControl, TemplateControl
        FixBeats/   FixBeatsSheet, TapPad, ManualTapFlow
        BigCount/   BigCountOverlay
    ImportKit/  BeatKit/  PlaybackKit/  VoiceKit/  ProjectStore/    (see §1)
    Resources/  Voices/…
BeatCountTests/     unit tests (BeatKit, timeline math, stores)
BeatCountUITests/   smoke flows
tools/analysis-oracle/   desktop Python venv (librosa/madmom) — dev-only, never ships
```

State: `@Observable` view models per screen; `PlaybackEngine` is a single actor-ish controller owned at the app level (it must outlive screen churn and host the audio-session observers). No third-party packages.

---

## 8. Testing Strategy

- **Beat detection vs. known-BPM oracle:** a desktop Python venv with librosa (ISC — the exact Ellis algorithm) and madmom as references (dev-only, sidestepping madmom's non-commercial model license). A fixture set of ~10 personal dance tracks + synthetic fixtures (click tracks at 60/90/120/128/174 BPM, with offsets, with swung eighths, with noise). CI-style unit tests assert: F-measure ≥ 0.9 within ±70 ms vs. librosa per track; BPM within one octave-fold of truth; correct octave on ≥ 8/10 real tracks; confidence low on the noise/speech fixtures. A small script exports librosa's beat lists to JSON fixtures consumed by Swift tests.
- **Pure-math unit tests (BeatKit):** correction transforms (halve/double/rotate/offset), "&" midpoint derivation incl. final-beat extrapolation, count-token math `((i − anchor) mod 8) + 1`, timeline rebuild at every rate, template switch at phrase boundary.
- **Sync verification (device, manual + scripted):** loop back device output into a recorder; measure voice-onset vs. click-track beat time at 0.5×/1×/1.25×; assert ≤ 30 ms and zero drift over 4 minutes. Repeat after seek, rate change, interruption, and route change.
- **Persistence tests:** round-trip project.json/beats.json; schema-version migration stub; missing-audio → hash-relink path; atomic-write crash simulation (write temp, kill, verify old state intact).
- **Import tests:** each UTType incl. MP4/MOV extraction, no-audio-track video, DRM `.m4p` rejection, duplicate hash, iCloud placeholder (manual), disk-full simulation.
- **UI smoke tests:** import → analyze → play → fix → relaunch-resumes flow on iPhone SE and Pro Max size classes.

---

## 9. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Hand-rolled detector accuracy mediocre → correction becomes the norm | Genre (steady dance music) is the easy case; octave scoring + prior; oracle-driven tuning; upgrade paths (Beat This! CoreML, iOS 27 Music Understanding) behind `BeatAnalyzer` |
| Voice↔beat drift > 30 ms (product-fatal) | Sample-time scheduling on a shared engine clock (not timers); time-pitch latency compensation; p-center alignment; recorded-output verification is a release gate |
| `AVAudioUnitTimePitch` phasiness at 0.5× | Acceptable for practice; tune `overlap`; drop-in upgrade: Signalsmith Stretch (MIT) in an `AVAudioSourceNode` — post-MVP only |
| Bluetooth latency corrupts tap corrections & display sync | `outputLatency` compensation + calibrated touch constant; Bluetooth warning caption; deterministic Shift-1 steppers as the latency-immune path; per-route offsets post-MVP if needed |
| Silent wrong grid for beginners (no forced verification) | Low-confidence/drift captions nudge exactly when the detector is unsure; Counts A/B makes verification trivial |
| Player density on small screens | Big Count overlay for practice; 4 s control dimming; SE-class layout in UI tests |
| Tempo-drift songs unfixable | Honest scoping: warning caption; global transforms only; per-section editing deliberately out |
| `stop()`-resets-timeline class of bugs | Single `rebuildPlayback()` path for every disruption; gotchas checklist in review + device tests |

---

## 10. Post-MVP Roadmap (brief)

1. **Offline export** (music + counts → M4A) — see appendix; ~100 lines on the existing graph.
2. **Mic recording** as an input source (same pipeline post-capture).
3. **More voices & locales** (Fiverr commercial-use recordings; manifest-driven content drops) and more templates (4-count, "5-6-7-8" lead-in, swing-aware "&").
4. **iOS 27 Music Understanding** analyzer (beats + bars → automatic downbeat) behind `BeatAnalyzer`; optional re-analysis prompt on engine upgrade.
5. Auto-suggest template from BPM; per-route latency offsets; loop-region drilling; background-audio entitlement + Now Playing.

*(YouTube download remains a permanent non-goal: YouTube ToS + App Store Guideline 5.2.3. Video-file import — already in MVP — is the sanctioned mitigation.)*

---

## Appendix A: Offline Export (post-MVP, kept cheap by design)

The live graph renders offline unchanged: `engine.stop()` → `engine.enableManualRenderingMode(.offline, format: AVAudioFormat(standardFormatWithSampleRate: 44100, channels: 2)!, maximumFrameCount: 4096)` → remake the same connections, schedule the music segment + all count events exactly as live (rate 1.0 or the drill rate) → loop `engine.renderOffline(…)` into an `AVAudioFile(forWriting:)` with AAC settings (`kAudioFormatMPEG4AAC`, 44.1 kHz, 192 kbps — AVAudioFile transparently encodes PCM writes) → `disableManualRenderingMode()` and rebuild the live session. Because playback and export consume the same count-event timeline and graph, the entire feature is the mode switch plus a progress UI.

## Appendix B: Rejected Alternatives (one line each)

- **aubio (GPL) / Essentia (AGPL) / madmom (NC models) / Superpowered (paid-only):** license-disqualified for App Store distribution.
- **AVPlayer + time observers for counts:** no shared sample clock — 10–50 ms jitter is audibly off-beat; export path diverges.
- **Timer-fired `AVAudioPlayer.play()` per count:** variable start latency; fails the sync bar.
- **SwiftData:** bulk arrays + one settings struct don't earn a database; JSON sidecars are simpler, debuggable, and format-portable.
- **Just-in-time look-ahead count scheduler:** the clean upgrade if full pre-scheduling ever hits limits; unneeded at ~1,000 shared-buffer enqueues.
