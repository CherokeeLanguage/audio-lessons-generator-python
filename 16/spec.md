# Spec — session-audio export switches to AAC .m4a with per-track bitrate ladder

Remote issue: https://github.com/CherokeeLanguage/audio-lessons-generator-python/issues/16

## Problem

Cloudflare Workers Static Assets — the deployment path for the site repository
(CherokeeLessons, CherokeeLessons#54) — enforces a 25 MiB per-file cap on
delivered assets. This generator's per-session audio export is mono speech
content; its longest sessions run ~60 minutes. The current export is LAME mp3
VBR (`-qscale:a 3` via `MP3_QUALITY = 3`, `main.py:1066`), landing at
~51–57 kb/s effective — that is a deliberate quality-3 VBR undershoot on
narrow-band mono speech, not a CBR rate. Measured consequences:

- the hour-long session files sit at the cap's edge (25 MB measured);
- higher-quality mp3 settings exceed the cap outright on those sessions
  (96k re-encode of the 42.8-min session: 30 MB; the 59.7-min one scales
  beyond);
- no mp3 setting both preserves the current effective rate and clears the
  cap with margin.

Transcode trials on the real tracks (2026-11-15, ffmpeg; three representative
tracks — `0001` 13.8 min, `0009` 42.8 min, and the 59.7-minute worst case
`0022`; see [research/bitrate-trials.md](research/bitrate-trials.md)) settled the
recommended deliverable: **AAC-LC**.

- Universal platform playback: every browser `<audio>` implementation
  (Chrome, Firefox, Safari/iOS, Edge, Android) plus native players — no open
  compatibility deltas (Opus would be marginally smaller but leaves
  Safari/iOS as an open question).
- Effective ~46–59 kb/s on this content across targets; the mp3 source's own
  information ceiling is ~57 kb/s, so ~58 kb/s effective is the maximum
  meaningful quality point — beyond it larger files carry no audible gain.
- Max measured file: 20 MB at a 96k target on the 59.7-minute session —
  clear margin under the 25 MiB cap.

The source upstream (per-sentence TTS clips) is itself 96 kb/s mp3, so the
deliverable remains lossy-mirror quality by construction; this spec governs
the single encode the shipped audio receives (one generation, no double
transcode).

## Scope

This repository — the per-session final-audio export path in `main.py`:

- `MP3_QUALITY` / `MP3_HZ` constants (lines 39–40) — replaced by the AAC
  settings;
- the session export call (`main.py:1066`, `combined_audio.export(...,
  format="mp3", parameters=["-qscale:a", ...])`);
- the session output filename (`{dataset}-{NNNN}.mp3`) and the `mp3/`
  directory reference it lives in;
- the `create_mp4` ffmpeg mux (`main.py:1112+`), which ingests the exported
  file and re-encodes with `-q:a 3`.

Upstream per-sentence clip caching (`tts.py`, mp3) is unchanged — it is a
cache class, not the deliverable. The srt/vocab/img pipelines are unchanged.

## Requirements

- **R-1 — .m4a export.** The per-session output SHALL be written as `.m4a` —
  AAC-LC in MP4 container, mono, 48 kHz — reusing today's tags/duration
  handling (`tags`, `tags["duration"]`).
- **R-2 — Per-track bitrate ladder.** The session file SHALL encode at a
  **128 kb/s** AAC target, and after encoding its size SHALL be checked: if
  the file exceeds **24 MiB**, the encode SHALL fall back to **112 kb/s,
  then 96 kb/s**, until the output passes the cap. The check is per session
  file and encode-and-measure — the native AAC encoder undershoots the
  nominal target on quiet mono speech, so final size, not nominal rate,
  decides the step. The export path SHALL record, per track, its ladder
  transcript — the rungs attempted, the measured size at each rung, and the
  chosen rung. (Cap rationale: 24 MiB leaves margin under the site's
  25 MiB asset cap for encoder and tooling rounding.)
- **R-3 — mp4 mux to stream copy.** `create_mp4` SHALL use the produced
  `.m4a` as its audio input and stream-copy the audio (`-c:a copy`),
  removing the `-q:a 3` re-encode — the mp4 then carries the identical,
  already-cap-compliant audio track (and one less lossy generation than
  today's re-encode).
- **R-4 — Output surface.** Only the audio filename extension changes
  (`.mp3` → `.m4a`); the directory layout (`mp3/` session directory, `img/`,
  `mp4/`, `srt/`, `vocab/`) and all non-audio outputs stay unchanged.

**Cross-repo consumer:** the site conversions of the lesson-audio pages
consume the same recommended settings inline in their own spec
(CherokeeLessons#54 — CLL-1's 23 sessions and animal-names' 9) — this ticket
is the owning definition of the encoder settings; a settings change here
revises that spec's conversion parameters too. The animal-names set (9
tracks, 12.8–29.9 min, 2.1–4.5 MB per file at source — every file far under
the cap) projects to ≈ 76 MB at the 128k rung (encoder-measured ≈ 2.3–2.4×
the mp3 sizes; no rung fallback).

## Success criteria

| ID | Criterion | Class | Instrument |
|----|-----------|-------|------------|
| SC-1 | A generator run produces session audio as `.m4a` (the production CLL-1 config yields 23 files named `cll1-v3-NNNN.m4a`) | behavioral | run the documented entry (`main.py`) against `configs/cll1-v3-cfg.json` in the repo's environment; glob the session output directory for `cll1-v3-*.m4a` and count = 23 |
| SC-2 | Each session `.m4a` is AAC-LC, mono, 48 kHz, in an MP4 container | behavioral | `ffprobe` each file: `codec_name= aac`, `channels= 1`, `sample_rate= 48000`, `format_name` contains `mov`/`mp4` |
| SC-3 | Every session file is ≤ 24 MiB | structural | `stat -c %s` ≤ 25,165,824 bytes per file |
| SC-4 | The mp4 mux stream-copies the session `.m4a` audio — no audio re-encode in the mux | structural | the mux command construction in `main.py` passes `-c:a copy` for the audio input and no longer carries the `-q:a`/`3` re-encode flags; `ffprobe` on a produced mp4: audio stream `codec_name= aac` |
| SC-5 | The repo's build gate passes with the change in place | structural | `./gradlew build` exit 0 |
| SC-6 | Each session file's final encode is the highest ladder rung (128 → 112 → 96 kb/s) whose encoded output measured ≤ 24 MiB — the ladder is actually exercised per track, never globally pre-lowered | behavioral | the export run's per-track ladder transcript (rungs attempted, measured sizes, chosen rung); cross-check per file: its `ffprobe` `bit_rate` corresponds to the recorded chosen rung |

## Out of scope

- The TTS per-sentence clip cache format (`tts.py`, mp3).
- Regenerating historical decks beyond the SC-1 verification run.
- The site-side conversions of the lesson-audio pages
  (CherokeeLessons#54 — consumes these settings).
- YouTube upload/mirror work for the mp4 outputs.

## Approach

Replace the mp3 export constants and call with the AAC settings and a
size-gated retry (encode at the current ladder rate, measure, step down if
over the cap); rename the session output extension; switch the mp4 mux to
stream-copy of the session audio. Verification runs the production CLL-1
config and probes the outputs.

## Impact

Consumers: the site's audio-exercise pages gain deployable, cap-compliant
session audio with better speech quality-per-byte than the current mp3 export
and no browser compatibility gaps. Projected payload across the 23 CLL-1
tracks (from the trials' measured rung rates; the implement-time ladder
transcript replaces the projection with measured outcomes): ≈ 432 MB total,
ladder outcome 15 tracks at the 128k rung / 8 dropping to the 112k rung /
none reaching the 96k rung, max file 23.9 MB — every file ≤ 24 MiB by
construction. Risk: low-medium — the export change is mechanical
(codec/container/filename plus a size-gated retry loop), deck regeneration
is deterministic from the existing assembly pipeline, and the mp4 mux
simplifies to a stream copy. Rollback: revert the commit; decks re-generate
under the prior mp3 settings from the same inputs.

## Evidence — decision basis (2026-11-15)

Measured on this machine (ffmpeg of `cherokee-diffwave` env) against
`CherokeeLessons/content/lesson-audio/cherokee-language-lessons-1---audio-exercises/`
cll1-v3-{0001,0009,0022}.mp3; full tables in
[research/bitrate-trials.md](research/bitrate-trials.md). Per-track profile
of all 23 shipped files: 13.8–59.8 minutes each, 51–57 kb/s effective.

> Full spec and plan artifacts: https://github.com/CherokeeLanguage/audio-lessons-generator-python/tree/issues-data/16
