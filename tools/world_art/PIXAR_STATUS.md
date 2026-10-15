# Pixar world-art redraw — done

**Date:** 2026-10-15 (Asia/Dubai)

- All 64 `img/world/**` pictures (26 letters, 10 animals, 9 counting objects, 5 country foods, 10 place icons, 4 prayer cards) were redrawn as glossy 3D Pixar-style art with GenerateImage, cut out with rembg and saved as 512x512 transparent WEBP by `process_pixar.py`.
- Objects have no faces (kitchen-card style); animals are friendly characters. No text in any picture.
- Shared pictures: numbers/apple = letters/a, numbers/ball = letters/b, numbers/fish = letters/f, letters/l = animals/lion, letters/z = animals/zebra.
- Redone after review: ladybug (now 6 legs), flag-quiz pennant (plain red/yellow instead of rainbow stripes), safari truck (generic toy design, no real-brand grille).
- Raw renders: `/workspace/world-art/pixar_raw/` (jobs by id). Contact sheet: `/workspace/app/world-shots/contact-sheet.png`.
- Note: GenerateImage now saves into the bot store `attachments/` folder under a different file name than the path it reports, so raw files were matched by building a numbered contact sheet of new files after each batch.
- Flags and the land map `.jpg` backgrounds were left as they were (maps still use small Fluent decorations; see `img/world/CREDITS.md`).
