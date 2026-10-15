#!/usr/bin/env python3
"""Generate kid-pitched Kokoro MP3 clips for Emmavengers House Adventure.

Usage:
  python3 tools/gen_voice.py jobs.json [--voice mia] [--outdir voice/mia]
  Env overrides: VOICE (kokoro id), SPEED, SH (pitch shift), VOICE_ID (friendly id)

jobs.json is a list of [text, outfile] OR [text, hash] (hash => <outdir>/<hash>.mp3).
An optional 3rd column gives Kokoro phonemes (IPA) to speak instead of the text, e.g. letter sounds
["a, a, apple!", "<hash>", "ˈæ, ˈæ, ˈæpəl!"]; the file name is still the hash of the text. lands.json keeps
these in its "phonemes" map.
"""
import sys, json, soundfile as sf, subprocess, os, argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KOK = Path(os.environ.get("KOKORO_DIR", "/workspace/kok"))

# Friendly voice pack: id -> (kokoro_voice, speed, pitch_shift, gender, label)
VOICES = {
    "mia":  ("af_heart",   0.72, 1.18, "girl", "Mia"),   # default — same pitch as before, ~10%+ faster
    "lily": ("af_jessica", 0.72, 1.28, "girl", "Lily"),
    "zara": ("af_bella",   0.78, 1.38, "girl", "Zara"),
    "sam":  ("am_puck",    0.70, 2.30, "boy",  "Sam"),
    "leo":  ("am_liam",    0.75, 2.20, "boy",  "Leo"),
    "max":  ("am_fenrir",  0.68, 2.10, "boy",  "Max"),
}
DEFAULT_VOICE = "mia"

def atempo_chain(factor: float) -> str:
    """ffmpeg atempo accepts 0.5–2.0; chain filters for larger/smaller factors."""
    parts, rem = [], factor
    while rem < 0.5 - 1e-9:
        parts.append(0.5); rem /= 0.5
    while rem > 2.0 + 1e-9:
        parts.append(2.0); rem /= 2.0
    parts.append(rem)
    return ",".join(f"atempo={p:.6f}" for p in parts)

def resolve_jobs(raw, outdir: Path):
    jobs = []
    for row in raw:
        if len(row) not in (2, 3):
            raise SystemExit(f"bad job row: {row!r}")
        text, second = row[0], row[1]
        ph = row[2] if len(row) == 3 else None
        if str(second).endswith(".mp3") or "/" in str(second):
            out = Path(second)
            if not out.is_absolute():
                out = ROOT / out
        else:
            out = outdir / f"{second}.mp3"
        jobs.append((text, out, ph))
    return jobs

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jobs")
    ap.add_argument("--voice", default=os.environ.get("VOICE_ID", DEFAULT_VOICE),
                    help="friendly voice id (mia/lily/...)")
    ap.add_argument("--outdir", default=None, help="output directory (default voice/<id> or voice/ for mia)")
    ap.add_argument("--kokoro", default=None, help="override Kokoro voice name")
    ap.add_argument("--speed", type=float, default=None)
    ap.add_argument("--sh", type=float, default=None, help="pitch shift (asetrate factor)")
    ap.add_argument("--force", action="store_true", help="regenerate even if file exists")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    vid = args.voice
    if vid not in VOICES and not (args.kokoro and args.speed and args.sh):
        raise SystemExit(f"unknown voice {vid!r}; known: {list(VOICES)}")
    kv, sp, sh, gender, label = VOICES.get(vid, (None, None, None, None, vid))
    kv = args.kokoro or os.environ.get("VOICE") or kv
    sp = args.speed if args.speed is not None else float(os.environ.get("SPEED", sp))
    sh = args.sh if args.sh is not None else float(os.environ.get("SH", sh))

    if args.outdir:
        outdir = Path(args.outdir)
        if not outdir.is_absolute():
            outdir = ROOT / outdir
    else:
        # Default Mia keeps flat voice/ path for backward compatibility + SW precache
        outdir = ROOT / "voice" if vid == DEFAULT_VOICE else ROOT / "voice" / vid
    outdir.mkdir(parents=True, exist_ok=True)

    raw = json.load(open(args.jobs))
    jobs = resolve_jobs(raw, outdir)
    if args.limit:
        jobs = jobs[: args.limit]

    # Prefer local kokoro copy under /workspace/kok; fall back to cwd
    model = KOK / "kokoro-v1.0.int8.onnx"
    voices = KOK / "voices-v1.0.bin"
    if not model.exists():
        model = Path("kokoro-v1.0.int8.onnx")
        voices = Path("voices-v1.0.bin")

    from kokoro_onnx import Kokoro
    k = Kokoro(str(model), str(voices))
    tmp = f"/tmp/k{os.getpid()}.wav"
    done = skip = 0
    af_tail = (
        f"asetrate={{sr}}*{sh},"
        f"aresample=24000,{atempo_chain(1/sh)},"
        "silenceremove=start_periods=1:start_threshold=-50dB,"
        "areverse,silenceremove=start_periods=1:start_threshold=-50dB,areverse,"
        "apad=pad_dur=0.15"
    )
    print(f"[gen_voice] voice={vid} kokoro={kv} speed={sp} sh={sh} out={outdir} jobs={len(jobs)}", flush=True)
    for text, out, ph in jobs:
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists() and not args.force and out.stat().st_size > 200:
            skip += 1
            continue
        if ph:
            a, sr = k.create(ph, voice=kv, speed=sp, lang="en-us", is_phonemes=True)
        else:
            a, sr = k.create(text, voice=kv, speed=sp, lang="en-us")
        sf.write(tmp, a, sr)
        subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-y", "-i", tmp, "-af", af_tail.format(sr=sr),
             "-ac", "1", "-b:a", "32k", str(out)],
            check=True,
        )
        done += 1
        if done % 25 == 0:
            print(f"  … {done} written, {skip} skipped", flush=True)
    print(f"[gen_voice] done voice={vid}: wrote={done} skipped={skip}", flush=True)

if __name__ == "__main__":
    main()
