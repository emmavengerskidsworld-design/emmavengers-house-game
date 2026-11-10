# Authoring guide — adding content to Emmavengers World

You only edit files in `content/src/`. Never edit `content/library/`, `content/registry.lock.json`,
`content/build-report.md` or `sw.js` by hand: they are generated. How it works: `docs/content-library.md`.

## The routine for ANY change

```bash
python3 tools/content_build.py      # 1. validate + build. Read the errors; fix; repeat until "OK"
                                    #    -> read content/build-report.md (plain summary, languages, warnings)
python3 tools/check_voice.py > missing.json   # 2. spoken lines without a voice clip (the build also tells you)
#    make the clips (tools/gen_voice.py, see README "Voice clips"); French: --kokoro ff_siwis --lang fr-fr
python3 tools/build_sw.py           # 3. offline cache list for the new files
python3 tools/run_tests.py          # 4. all tests (validator first). --quick for a 20-second check
git add -A && git commit            # 5. commit content/src AND the generated files together
```

Optional: `python3 tools/run_tests.py --install-hook` makes git run the quick tests before every commit.

## Rules the validator enforces (so you don't have to remember them)

- **Ids** `ew.<type>.<name>`: lower case, digits, dashes, dots. The prefix must match the type
  (`ew.quiz.*` is a quiz-item, `ew.country.*` a country …). Never rename or reuse an id: to replace a record,
  give the new one a new id and set the old one to `withdrawn` (or delete it — its id is then retired forever).
- **Texts** are `{"en": "...", "fr": "..."}` with tags from `content/src/locales.json` only. Every language listed in
  the pack's `locales.required` must be present in every text. `{placeholders}` must match across languages.
  No HTML or script, except bold `<b>` where `capabilities.json` allows it (letter cards).
- **Facts need sources**: a factual quiz item or learn card must cite `ew.source.*` records (URL + date checked).
- **References** must point at records that exist, of the right type, in the same pack or in `core`.
- **Tags** come from `content/src/taxonomy.json` (age bands `5-7`, `8-10`, `11-13`; regions; subjects; difficulty
  `starter`/`core`/`stretch`; modes). Add a new value there first if it is truly needed.
- **Status**: start at `draft`. The preview site shows drafts; the live channel ships only `published`.
- **Files**: every picture and voice clip a record uses must exist; every spoken line must have its clip.
- **Activity types** must be ones the player supports (`content/src/capabilities.json`).

## Add a country

1. Copy the pilot: `cp -r content/src/countries/cameroon content/src/countries/<slug>` (slug: lower-case English name, e.g. `kenya`).
2. In **every** file of the new folder, replace ids: `pilot-cameroon` → `<slug>` (or `pilot-<slug>`), `ew.country.cameroon`
   → `ew.country.<slug>`, `country.cameroon` → `country.<slug>`. Ids must be unique across the library.
3. `pack.json`: `id` `country.<slug>`, `collection` the region (`countries.africa`, `countries.americas`,
   `countries.asia`, `countries.europe`, `countries.oceania`), `summary` `ew.country.<slug>`, the `defaults.tags.regions`,
   `locales.required` (the languages that must be complete), and `"preload": false` (only the pilot is a starter pack).
4. `country.json`: name per language, ISO 3166-1 code in `externalIdentifiers`, flag, hub lines, learn/play/quiz/stories lists.
5. Replace every text and fact; add `sources.json` records for every fact (URL, date checked, publisher). Keep `status: draft`.
6. Add a place in World Land (`content/src/core/lands.json`, record `ew.land.world`, `places`):
   `{"key": "<slug>", "name": {"en": "Kenya"}, "sub": {"en": "Learn · Play · Quiz · Stories"}, "icon": "img/world/countries/<slug>-flag.webp", "type": "country", "country": "ew.country.<slug>", "x": 50, "y": 30}`.
7. Run the routine above. A country test can copy `tools/test_cameroon.py`.
8. When the reviews are done (facts, educator, cultural, language, Emmanuel): set statuses to `published`.

## Add a language

1. `content/src/locales.json`: add `{"tag": "sw", "name": "Kiswahili", "dir": "ltr", "status": "in-review"}`
   (BCP 47 tag; `dir` `rtl` for Arabic, Hebrew…). Status `active` = ready for children; `in-review` = drafts.
2. Add the language to texts: `{"en": "Hello", "fr": "Bonjour", "sw": "Habari"}`. The build report shows coverage per pack.
3. When a pack is complete in that language, add it to that pack's `locales.required` — from then on the build fails
   if a text is missing. Record per-language review state in `l10n`, e.g. `"l10n": {"sw": {"status": "draft"}}`.
4. Voice for the new language is Stage 2 (the voice engine). Until then, do not set `active` for a language without clips.

## Add or change a land, a place, a deck item, a Study shelf

- Lands: `content/src/core/lands.json` (one `land` record each) and the order in `content/src/core/world.json`
  (`payload.lands`). A land needs a map picture, a color, a music theme and its places.
- Places: `type` `link` (opens a game module), `cards` or `quiz` (with a deck), `count`, `country`.
- Deck items (letters, numbers, animals, country cards, prayers): `content/src/core/decks.json`. Facts need sources.
- Study shelves: `content/src/core/study.json`.
- Letter sounds (IPA for the voice): `content/src/core/lexicon.json`.

## Add a game (activity)

- Using an existing type (`grid-route.v1`, `ordered-slots.v1`, `match.v1`, `map-select.v1`, `evidence-comparison.v1`,
  `inquiry.v1`): add an `activity` record in the country's `play.json` and list it in the country's `play` list.
- A **new** type needs code: add it to `content/src/capabilities.json`, to `TEMPLATES` in `library.js`, write the player in
  `country.js`, and bump `player` in `build.json` if old apps must not receive it. Old app versions skip packs that need
  types they don't know (they never crash on them).

## Statuses and reviews

`draft` (being written) → `checking` (sent to reviewers) → `changes-requested` → `reviewed` → `approved` (Emmanuel) →
`published` (on live). `withdrawn` removes it from children at once (the build blocks anything still using it);
`archived` keeps history only. Write who reviewed what in `review` (`records`, `note`) and per language in `l10n`.

## Publishing to the live site

`main` is the live site (GitHub Pages), so on `main` the build setting `channel` in `content/src/build.json` is `live`
(published records only). The test site must be built with `python3 tools/content_build.py --channel preview`
(drafts included). Release 1 (2026-11-10): the Cameroon pilot, Ari/Ezra and the country-player buttons were approved
for live by Emmanuel CLETUS, with French pending fluent review, placeholder art and synthetic voices recorded in each
record's `review`. The hub's "Draft for testing" badge only shows for a country that is not `published`.

