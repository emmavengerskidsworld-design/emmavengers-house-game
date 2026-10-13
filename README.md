# Emmavengers House Adventure

Kids' learning game (GitHub Pages): https://emmavengerskidsworld-design.github.io/emmavengers-house-game/

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
