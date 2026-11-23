# Hindsight: design brief (draft for review)

## Who and what
**Audience:** a shop or small-business owner or manager, not a data scientist; also a reviewer judging craft.
**Job of the product:** let someone decide how far to trust a forecast, in under two minutes, by watching it replay against real history.
**Feeling:** calm, confident, a little cinematic. "Rewind and see." Professional enough for a boardroom, simple enough for a shop counter.

## The memorable thing
**The curtain.** On the replay stage there is a "today" marker. Everything to its right is hidden behind a soft curtain, and the forecast opens ahead of it like a fan whose width is the model's uncertainty. Press play and the curtain lifts day by day: the real sales line draws in, and a small tick lands under each day (inside the range or missed). By the end you can see the track record as a ribbon of hits and misses. Nothing else in the app competes with this.

## Palette (draft)
- **Page:** a cool, quiet light grey `#F4F5F7`; text in deep ink `#16202E`.
- **Stage (the replay panel only):** deep lapis `#0F1B45`, so the chart glows like a screen and pulls the eye.
- **Forecast:** lapis-blue fan on the stage (`#8EA2FF` line, translucent bands).
- **Actual sales:** saffron `#F4B23E`, the one warm colour, always meaning "what really happened".
- **Hit / miss:** teal `#1E9E86` / coral `#E0553F`, always with a shape (check and cross) as well as colour.
- **Accent for buttons and links:** lapis `#2740C9`.

Dark stage plus light page is deliberate: one panel is the product, the rest is calm.

## Type
- **Headings and numbers:** Cairo (covers Latin and Arabic in one voice).
- **Body:** IBM Plex Sans and IBM Plex Sans Arabic.
- Large tabular numerals for the key readouts; line lengths under about 70 characters.

## Layout
```
+----------------------------------------------------------+
|  Hindsight        Replay   Scorecard   Next week   EN|ع  |
+----------------------------------------------------------+
|  Your sales: Pharmacy A, daily, 2 years   [change file]   |
|                                                          |
|  +----------------- STAGE (lapis) --------------------+  |
|  |   ...history line...|  today  ░░░ curtain ░░░░░░░   |  |
|  |                     |  fan opens ->                 |  |
|  |   [<<] [play] [>>]  speed   ----o---- scrub         |  |
|  |   track record ribbon:  ✓✓✓✗✓✓✓✓✗✓✓✓✓✓               |  |
|  +----------------------------------------------------+  |
|  "On this day the forecast said 120 to 168; actual 151"  |
|  How much to trust it:  range held 79% of days           |
+----------------------------------------------------------+
```
Three main screens: **Start** (drop a file, confirm columns, or try the sample), **Replay** (the stage), **Scorecard** (does the clever model beat the simple rule, and when does it fail). A **Next week** view shows the live forecast with its range once the user trusts it.

## Behaviour and motion
- One orchestrated moment: the curtain lift and the fan opening when play starts. Everything else is still and quick.
- Controls respond instantly; replay is smooth at up to 20 days per second.
- Respect reduced-motion (the curtain then simply steps).
- Keyboard-first: space plays, arrows step, every control reachable.

## Writing
Plain verbs, sentence case, no hype. Examples: "The forecast was right 4 days out of 5." "This item has too little history for a reliable forecast. Add about 3 more months." Errors say what happened and how to fix it. No "AI-powered".

## Quality bar
Checked in a real browser at desktop and phone widths, in both themes where applicable, with automated and manual accessibility audits (contrast, names, landmarks), keyboard paths tested, bilingual layout checked for right-to-left, performance measured. Every figure is labelled prediction, actual, or recorded benchmark.

## Review against the generic default
A generic version of this would be a dark dashboard with a glowing accent, a row of cards of KPIs, and a line chart. This one differs by having one dark stage on a light page, a curtain that hides the future, a track-record ribbon, one warm colour reserved for reality, and bilingual, right-to-left support designed in from the start. If anything here still looks like a template once built, it gets revised.
