# Piper (local text-to-speech)

The `/api/voice/speak` endpoint shells out to the Piper binary placed **here**.
These files are intentionally **not** committed (large binaries / models) — see
`.gitignore`. Install them once:

1. Download the latest Windows Piper release:
   https://github.com/rhasspy/piper/releases
   Extract so that this path exists:
   `backend/voice/piper/piper.exe`

2. Download a voice model + its config from:
   https://huggingface.co/rhasspy/piper-voices
   Recommended: `en_US-lessac-medium`. Place both files here:
   - `backend/voice/piper/en_US-lessac-medium.onnx`
   - `backend/voice/piper/en_US-lessac-medium.onnx.json`

After that, `GET /api/voice/status` should report `"piper_installed": true`.
