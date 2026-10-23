# Meme indexing and limits

Directory: AstrBot/data/plugin_data/astrbot_plugin_fish_capabilities/memes/. manifest.json is an array of entries with id/category/file/tags/description/image_text/usage_notes/approved/sha256. Images are stored in category folders with paths relative to the library root.

Eight categories: happy, comfort, tease, confused, greeting, goodnight, sad, acknowledge.

Local import from the repository root (no message is sent):

```bash
python -m tools.import_meme /path/to/approved.png --library /path/to/AstrBot/data/plugin_data/astrbot_plugin_fish_capabilities/memes --category happy --tags '开心,庆祝' --description '表达开心和庆祝' --approve
```

Manually add image_text (actual text) and usage_notes (appropriate/inappropriate situations), checking accuracy. A title is not verified OCR. The importer checks format, 4 MB and duplicate images. Runtime checks approval, containment and SHA256.

The model searches fish_meme_catalog(category, query) by tags, actual text and situation, then selects an exact image with fish_meme(category, meme_id). It does not invoke vision for every message or send a random image because a limit allows it.

0.4.0 defaults to 0 turn spacing and 0 time cooldown, retaining 6/hour, no same image for 1 hour, and 1/reply. The model decides whether and what to send. Existing installations must set meme_min_reply_gap and media_cooldown_seconds to 0 manually. Stricter spacing is configurable; explicit requests skip soft spacing only, retaining per-turn, hourly and duplicate limits.

Reference: [deepseek-chan-meme-pack](https://github.com/the-beating-light-of-the-nail/deepseek-chan-meme-pack). Third-party images are not redistributed; verify sources and rights before import. The original device's 74-image library is excluded.
