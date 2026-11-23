# App notes (M4 to M6)

## Redesign (after M5, at the owner's request)
The first interface was an upload-first landing page, a dark blue stage with an indigo accent, and a replay at the centre of everything. It was replaced by:
- **A dashboard front door like SENTINEL's.** The app opens on the bundled sample with no upload screen. Screens: Dashboard, Items (and an item page), Replay lab, Scorecard, Data. The replay is one lab among these.
- **A neutral palette**: warm-grey paper, dark ink, teal for forecasts, ink for real sales, green/amber/red with shapes for status. No blue-purple, no saffron, no dark stage. Headings in IBM Plex Sans Condensed, body in IBM Plex Sans.
- **Loading your own file moved to the Data page**, where it belongs.
- **New backend pieces**: `/dashboard` (headline numbers, one row per item, recent unusual days), `/total` (all items added together, with its own honest range because summed item ranges would not be valid), and an `item` filter on `/alerts`.
- Browser audit after the redesign: axe WCAG A/AA, including contrast, found no violations on any of the six screens in English light and Arabic dark. 97 Python and 22 front-end tests pass.

## What was checked, and how
| Check | Result |
|---|---|
| Backend tests (importer, service, API, cache) | 97 Python tests pass in total |
| Front-end tests (stage model, formatting, screens, translations) | 21 pass |
| Accessibility, axe-core WCAG 2.0/2.1 A and AA, **including real colour contrast**, in a real browser | No violations on Start, Replay, Scorecard and Next week, in English and Arabic, light and dark themes |
| Phone width (375 and 390 px) | No horizontal overflow (measured from element boxes) |
| Right-to-left | `dir="rtl"` and `lang="ar"` set; element boxes stay inside the viewport; keyboard, tables and forms use logical CSS properties |

## What was not checked
- **The Arabic text was written by me and has not been reviewed by a native speaker.** It should be read through before it is shown to anyone. Every string is in `web/src/i18n/ar.ts`.
- I could not take a clean screenshot of the right-to-left pages: the browser tool I used crops them. The right-to-left layout was verified from element positions and the accessibility audit, not by eye.
- No real-device testing (phones, Safari, Firefox). Only a Chromium-based browser.
- Nothing has been tried with a real Egyptian shop's file.

## Decisions
- **Charts keep time running left to right in Arabic.** The stage, ribbon and bar tracks are drawn in a left-to-right box; everything around them (text, tables, buttons) mirrors. This is common in Arabic dashboards, and arrows on the keyboard follow the chart, not the page direction.
- **Numbers use Western digits (0 to 9) in Arabic** (`ar-EG-u-nu-latn`), so figures match exports and spreadsheets. Dates use Arabic month names.
- **Server messages carry a code and numbers** (`code`, `params`), and the interface writes the sentence in the current language. A message with no known code falls back to the server's English text.
- **Plain-language method names are translated in the interface only**; the research code keeps its English names.

## Performance (measured, `scripts/time_analysis.py`)
Full analysis of the bundled sample (10 stores, 1,941 days, 6 methods, 28-day forecasts):

| Phase | Time |
|---|---|
| Replaying all methods | 57 s (53 model refits; about 38 s is LightGBM training, 8 s is building model inputs) |
| Ranges and scoring | 7 s |
| **Total, first run** | **65 s** |
| Same analysis again (disk cache) | **0.4 s** |

The cache is used only for the bundled sample. Uploaded files are held in memory and are never written to disk. Cache files are pickles written by this program, kept under `artifacts/cache/` (git-ignored).

I did not speed up the model itself: changing its thread count could change results slightly, and the documented numbers in `docs/EXPERIMENTS.md` were produced with the current settings.

## Known limits
- Item-level (one product per series) files with many hundreds of series are not tuned for speed; the importer keeps the 100 biggest items.
- The interface has no daily-to-weekly option: files must be daily.
- Holiday calendars are chosen by the user; the app does not decide that the Egyptian calendar helps.
