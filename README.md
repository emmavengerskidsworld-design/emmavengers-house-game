# Emmavengers World

Kids' learning game (home = Emmavengers World map; the Emmavengers House Adventure lives in Faith Land) (GitHub Pages): https://emmavengerskidsworld-design.github.io/emmavengers-house-game/

## Offline (PWA)
- `manifest.json` + `icons/` make it installable ("Add to Home Screen", standalone).
- `sw.js` is a service worker that, on the first online visit, precaches **every** asset
  (index.html, all `img/` incl. plain pictures and Bible pages, all `voice/` clips) in batches of 12 with 3 retries.
  After that every room, level and story works with no internet. Audio Range requests are answered from cache.
- Updates: the cache is named `emma-house-<build id>`. When online, the browser fetches the new `sw.js`
  in the background, downloads only changed files (unchanged ones are copied from the old cache),
  then the new version is switched in the next time the game is opened and old caches are deleted.

### Bible Library books (offline)
- **Core precache** (installed on the first online visit): the app, all rooms, Morning Routine, default Mia voice and every Bible book **cover**.
- **Each Bible book** (`img/bible/<slug>/*` + its narration clips) lives in a separate `emma-books` cache that survives app updates. A book is cached in full the first time it is opened online, and **every book listed in `bible-manifest.json` is prefetched in the background whenever the game is online** — so newly published books download automatically. A book re-downloads only when its version hash changes.
- Other voice packs (Lily, Zara, Sam, Leo, Max) stay on demand.
- After adding a book: `python3 tools/build_sw.py` (writes `sw.js` + `bible-manifest.json`), then `python3 tools/test_offline_bible.py` (one online visit → airplane mode → home, library, every book with pages + voice + quiz).

## After ANY change (new room, images, voice clips, index.html)
```
python3 tools/check_voice.py      # lists every spoken line without a voice/<fnv>.mp3 clip (must be 0)
python3 tools/build_sw.py         # regenerates sw.js: precache list + new build id
python3 tools/test_offline.py     # optional: offline Playwright test
```
`sw.js` is generated: never edit it by hand, and always rebuild it before committing, or phones keep the old version.
Voice clips: Kokoro `af_heart`, speed 0.53 (~125 wpm, a good pace for young kids), pitched up 1.18, +150 ms trailing silence: `tools/gen_voice.py jobs.json` (list of [text, voice/<hash>.mp3]; needs kokoro-v1.0.int8.onnx + voices-v1.0.bin). File name = FNV-1a hash of the exact text.

## Emmavengers World (home screen)
- `world.js` + the content library (`content/src/core`, see below): the app opens on a world map shaped like Africa with five lands. Each land opens its own
  inner map (`img/world/<land>-land.jpg`) with tappable places and its own soft WebAudio music theme (`music` in the land record).
  Back: activity -> land -> world map -> exit (header back, "Back to Map", Android `emmaBack()` and browser history back).
- **Faith Land**: Emmavengers House (all rooms + levels), Bible Land (Bible Library), Mia's Day (Morning Routine), Prayer Corner.
- **Letter Land**: ABC Sounds (A–Z cards, letter + sound + 3D picture) and Letter Hunt (first-letter quiz).
- **Number Land**: 1 to 10 cards and Count It! (tap each object to count, pick the number).
- **Nature Land**: Animal Safari (10 animals + fun facts) and Animal Quiz.  **World Land**: Country Cards (flag, greeting, food) and Flag Quiz.
- Add content without code: new deck items in `content/src/core/decks.json` (letters/numbers/animals/countries/prayers), new places
  in `content/src/core/lands.json` (types `link`, `cards`, `quiz` with mode `letter|pic|flag`, `count`) or a whole new land.
  Then `python3 tools/content_build.py` (validates + builds), voice clips (`python3 tools/check_voice.py > missing.json` ->
  Kokoro for all 6 voices with `tools/gen_voice.py`; IPA for letter sounds lives in `content/src/core/lexicon.json`),
  `python3 tools/build_sw.py`, `python3 tools/run_tests.py`. Step-by-step: `docs/authoring-guide.md`.
- Art: maps rendered by `tools/world_art/make_maps.py`, cards by `tools/world_art/make_cards.py` (3D objects from Microsoft Fluent Emoji 3D,
  MIT; flags drawn to the official designs). See `img/world/CREDITS.md`.

## Content library (Stage 1) — all lands, decks, countries
All content is data in one versioned library; the screens never hard-code content. Design: `docs/content-library.md`;
how to add a country, language, land or game: `docs/authoring-guide.md`.
- `content/src/` — what people edit: one folder per pack (`core/`, `countries/<slug>/`), each with a `pack.json`. Every
  record has a stable id (`ew.<type>.<name>`), status (draft → … → published), tags (age bands, subjects, land, regions,
  difficulty), sources, review notes and its texts per language (`{"en": "...", "fr": "..."}`).
- `content/schema/v1/` — JSON Schemas (Draft 2020-12) for every file and record type.
- `python3 tools/content_build.py` — validates everything (schemas, ids, languages, sources, references, voice clips,
  safety) and builds `content/library/` (small catalog + per-region indexes + per-pack files named by content hash),
  `content/registry.lock.json` (revisions, retired ids, releases) and `content/build-report.md` (plain-language report).
  `--check` is the required test: it fails if content is invalid or the built library is out of date.
- `library.js` — the app's loader: downloads only what changed, verifies every file's SHA-256, keeps a copy on the
  device (IndexedDB) for offline use, keeps the previous release for rollback, and has a query API. It rebuilds the
  old shapes (`LANDS`, the country pack) so `world.js` and `country.js` work unchanged.
- Old files `lands.json` and `content/countries/*.json` were migrated losslessly (`tools/content/migrate_v0.py`); the
  originals are frozen in `tools/fixtures/legacy-v0/` and the tests prove the app still receives exactly that data.
- Tests: `python3 tools/run_tests.py` (validator first, then content, loader and all game suites; `--quick`, `--scale`).

Progress is stored only on the device (`localStorage` keys `emmaCtry`, `emmaCtryPrefs`): visit stamp, quiz item ids seen today, no personal data.
