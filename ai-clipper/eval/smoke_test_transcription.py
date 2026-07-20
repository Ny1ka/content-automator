"""Phase 1 smoke test: exercises chunking, silence detection, and disk caching
end to end on synthetic fixtures (no real VOD required). This is a mechanics
check, not the accuracy acceptance test from the build spec — that needs real
VODs with known speech/silence to spot-check against by ear, and is still
pending (see PHASE1_REPORT.md).
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from transcription import transcribe
from transcription.silence import detect_silences

VODS_DIR = Path(__file__).resolve().parent / "vods"


def check(label: str, cond: bool):
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {label}")
    return cond


def main() -> int:
    ok = True

    # Tone/silence synthetic file: tone(8s) silence(3s) tone(8s) silence(4s) tone(8s)
    tone_path = VODS_DIR / "synthetic_test.wav"
    sils = detect_silences(str(tone_path), noise_db=-30, min_duration=1.0)
    ok &= check("silence detection finds 2 known gaps", len(sils) == 2)
    ok &= check("silence #1 near [8, 11]", abs(sils[0]["start"] - 8) < 0.5 and abs(sils[0]["end"] - 11) < 0.5)
    ok &= check("silence #2 near [19, 23]", abs(sils[1]["start"] - 19) < 0.5 and abs(sils[1]["end"] - 23) < 0.5)

    r1 = transcribe(str(tone_path), model_size="tiny", chunk_len=12, overlap=3, force=True)
    ok &= check("chunked transcribe produces silences field", len(r1["silences"]) == 2)
    ok &= check("chunked transcribe produces no false speech on pure tones", len(r1["segments"]) == 0)

    t0 = time.time()
    r2 = transcribe(str(tone_path), model_size="tiny", chunk_len=12, overlap=3)
    cached_elapsed = time.time() - t0
    ok &= check("second run hits cache (< 1s, identical result)", cached_elapsed < 1.0 and r1 == r2)

    # Real speech fixture (generated via macOS `say`, not checked into git if regenerated).
    speech_path = VODS_DIR / "synthetic_speech.wav"
    if speech_path.exists():
        r3 = transcribe(str(speech_path), model_size="small", force=True)
        words = [w for seg in r3["segments"] for w in seg["words"]]
        ok &= check("speech fixture produces word-level timestamps", len(words) > 5)
        ok &= check("word timings are monotonic and non-negative", all(
            words[i]["start"] >= 0 and words[i]["end"] >= words[i]["start"] for i in range(len(words))
        ))
    else:
        print("[SKIP] speech fixture not present, skipping speech assertions")

    print("\nALL PASS" if ok else "\nSOME FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
