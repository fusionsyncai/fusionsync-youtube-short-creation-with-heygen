# Memory

Persistent archive of every short-form video produced in this repo.

## Structure

```
memory/
├── README.md                  # this file
├── templates/
│   └── video-template.md      # copy this for every new video
└── videos/
    └── YYYY-MM-DD-<slug>.md   # one file per video
```

## Conventions

- **Filename:** `YYYY-MM-DD-<kebab-slug>.md` (e.g. `2026-05-31-phone-battery-myth.md`).
- **One video = one file.** Never combine.
- Fill out the frontmatter so videos are easy to grep/filter later (`platform`, `niche`, `status`, `tags`).
- Keep the original (raw) source content in the file too — useful for remixes and series.

## Why a memory folder?

1. **Tone consistency** — the agent re-reads past scripts to match your voice.
2. **Topic reuse** — quickly find related videos for series, follow-ups, or pinned-comment cross-links.
3. **Performance review** — log `views`, `ctr`, `retention` after publishing to learn what works.

## How the agent uses this

When you provide new video content, the agent will:

1. Generate Title + Voice Script + Description per the rules in `.cursor/rules/`.
2. Save the deliverables into a new `memory/videos/YYYY-MM-DD-<slug>.md` using the template.
3. Reference older entries in `memory/videos/` to keep tone and avoid duplicate topics.
