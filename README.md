# FusionSync — YouTube Shorts with HeyGen

Pipeline for generating short-form videos (YouTube Shorts + Instagram Reels) using HeyGen's API.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in your keys
```

## Daily workflow

```
You paste raw video content
        |
        v
Agent writes Title + Voice Script + Description
        |
        v
Saved as memory/videos/YYYY-MM-DD-<slug>.md
        |
        v
python scripts/generate_video.py memory/videos/<file>.md
        |
        v
MP4 lands in output/<slug>.mp4
```

## Commands

```bash
python scripts/generate_video.py memory/videos/2026-05-31-meta-ads-funnel-leak.md
python scripts/generate_video.py path/to/file.md --dry-run        # validate + estimate credits only
python scripts/list_avatars.py                                    # find an avatar_id
python scripts/list_voices.py --language English --gender male    # find a voice_id
```

## Hard rules baked into this repo

| Rule | Where |
| --- | --- |
| Voice script <= 50s / 125 words / one paragraph | `.cursor/rules/voice-script.mdc` |
| Description has 120%-speed timestamps + hashtags | `.cursor/rules/description.mdc` |
| **Every HeyGen render <= 17 credits** | `.cursor/rules/heygen-credits.mdc` + `generate_video.py` guard |
| Every video archived as `memory/videos/<slug>.md` | `.cursor/rules/youtube-shorts-workflow.mdc` |

## Project layout

```
.cursor/rules/        persistent AI rules (auto-loaded)
memory/
  README.md
  templates/
    video-template.md
  videos/
    YYYY-MM-DD-<slug>.md
scripts/
  generate_video.py   main generator (with 17-credit cap)
  list_avatars.py
  list_voices.py
output/               rendered MP4s (gitignored)
.env                  secrets (gitignored)
.env.example          template
requirements.txt
```
