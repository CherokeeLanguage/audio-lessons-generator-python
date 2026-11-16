# Bitrate trials — CLL-1 session audio transcode comparison (2026-11-15)

Test tracks: `cll1-v3-0001.mp3` (5.7 MB, 13.8 min, 57.2 kb/s), `cll1-v3-0009.mp3`
(17 MB, 42.8 min, 53.6 kb/s), `cll1-v3-0022.mp3` (25 MB, 59.7 min, 56.9 kb/s),
from `CherokeeLessons/content/lesson-audio/cherokee-language-lessons-1---audio-exercises/`.
Encoder: ffmpeg (env `cherokee-diffwave`); AAC = native ffmpeg `aac` encoder.
All mono 48 kHz; all 23 shipped sessions profiled at 51–57 kb/s effective
(bitrate spread is track length, not rate).

| Setting (mono) | 0001 (13.8 min) | 0009 (42.8 min) | 0022 (59.7 min, worst case) |
|---|---|---|---|
| source mp3 (LAME q3 VBR) | 5.7 M / 57 kb/s | 17 M / 53.6 kb/s | 25 M / 56.9 kb/s |
| AAC 64k | 2.5 M | 6.8 M | 13 M |
| **AAC 96k** | — | — | **20 M** |
| AAC 128k | — | — | 26 M (over 25 MiB cap) |
| Opus 64k | 4.6 M | 15 M | ~21 M (projected) |
| Opus 80k | — | — | 24 M (marginal) |
| mp3 CBR 64k | 6.3 M | 20 M | — |
| mp3 CBR 80k | 7.9 M | 25 M | — |
| mp3 LAME -q3 | 5.7 M | 17 M | — |
| mp3 LAME -q5 | 4.9 M | 15 M | — |

Findings:
- AAC LC chosen: universal playback, ~equal size to Opus at usable settings,
  max file 20 MB (96k) on the longest session.
- Quality ceiling: source tops at ~57 kb/s; ~58 kb/s effective is the max
  meaningful rate (beyond it, no audible gain; 25 MiB cap enforces it).
- Per-track ladder: 128k → 112k → 96k until file ≤ 24 MiB (encode-and-measure;
  native AAC undershoots nominal target on quiet mono speech).
- mp3 re-encode cannot reach equivalent quality under the cap (96k+ fails;
  -q5 ≈ half size of -q3 but double-lossy and still no margin headroom).
