# Japanese lyric backend API (ja)

For NVS Karaoke Studio PRO's local backend integration.

Both POST /api/projects/{id}/transcribe and POST /api/projects/{id}/align
now accept "language": "ja" in addition to vi, en and auto.

The underlying whisper-timestamped and stable-ts adapters were already multilingual.
This change exposes the language via request validation; it does NOT change model weights
or guarantee perfect Japanese word segmentation, especially in unspaced lyrics.
Keep Japanese phrases with intended token boundaries where possible when creating
reference lyric text, then review each word in the editor.

Run:
    python -m unittest tests.local_studio.test_japanese_api -v
    python -m unittest discover -s tests/local_studio -v

Important: tests mock AI models. Validate on an actual Japanese song with installed
models on Windows before claiming full Japanese transcription performance.
No Claude UI or frontend files changed.
