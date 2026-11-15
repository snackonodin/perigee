"""Generate the demo-video voice-over with ElevenLabs text-to-speech (dev tool, not the app).

usage: python scripts/voiceover.py <script.txt> <out_dir> <voice_name> [<voice_id>]

One request per line of the script, each told what comes before and after (request
stitching) so the lines sound like one take. The API key is read from ELEVENLABS_API_KEY,
loaded from the project's .env (git-ignored); it is never printed or written anywhere else.
Install: pip install -r requirements-tools.txt (kept out of the app's requirements.txt).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from elevenlabs import ElevenLabs, VoiceSettings

VOICES = {  # pre-made voices (usable on the free plan)
    "george": "JBFqnCBsd6RMkjVDRZzb",  # male, narrative
    "sarah": "EXAVITQu4vr4xnSDxMaL",  # female, soft
}
MODEL = "eleven_v4"


def main() -> None:
    script, out_dir, name = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
    voice_id = sys.argv[4] if len(sys.argv) > 4 else VOICES[name]
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    # The SDK's default api_key is read at import time, before .env is loaded here.
    client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])
    lines = [ln.strip() for ln in script.read_text(encoding="utf-8").splitlines() if ln.strip()]
    out_dir.mkdir(parents=True, exist_ok=True)
    for i, line in enumerate(lines):
        audio = client.text_to_speech.convert(
            text=line,
            voice_id=voice_id,
            model_id=MODEL,
            output_format="mp3_44100_128",
            previous_text=" ".join(lines[:i]) or None,
            next_text=" ".join(lines[i + 1:]) or None,
            voice_settings=VoiceSettings(stability=0.55, similarity_boost=0.75),
        )
        target = out_dir / f"l{i + 1}.mp3"
        with target.open("wb") as fh:
            for chunk in audio:
                fh.write(chunk)
        print(f"{name}: line {i + 1}/{len(lines)} -> {target.name}")  # noqa: T201 (CLI progress)


if __name__ == "__main__":
    main()
