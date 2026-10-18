# UI UX Pro Max: project-local installation

The owner explicitly requested this skill and asked to stop using the earlier
UI/UX skill as the design basis.

- Source: https://github.com/nextlevelbuilder/ui-ux-pro-max-skill
- Inspected commit: `56ea9cf174ed86786187daa9de0e6247cb0747e4`
- Upstream CLI package version in that checkout: `2.5.0`
- License: MIT; upstream license retained with the local installation.
- Installed directory: `.agents/skills/ui-ux-pro-max/` within this project.
- Entry: `.agents/skills/ui-ux-pro-max/SKILL.md`.
- Installation method: cloned the requested repository, inspected its Codex
  platform template and renderer, rendered that template with Quick Reference,
  and copied upstream standard-library Python scripts plus local CSV data. No
  global npm CLI, operating-system package or unrelated skill was installed.
- The local installation is excluded through `.git/info/exclude`; it is not an
  application dependency or part of the user-facing app package. A fresh checkout
  needs its own installation. This records a Cloud project install, not a global
  installation in the owner's Mac Codex app.

The source's Codex configuration installs to `.agents/skills/ui-ux-pro-max`, not
the older `.codex/skills` layout. The skill was read and used directly this round;
automatic discovery in another process/session has not been independently tested.

## Verified use in this review

Run from the project root:

```bash
python3 .agents/skills/ui-ux-pro-max/scripts/search.py 'glassmorphism' --domain style --full -n 1
python3 .agents/skills/ui-ux-pro-max/scripts/search.py 'video editor' --domain product -n 1
python3 .agents/skills/ui-ux-pro-max/scripts/search.py 'loading buttons error feedback' --domain ux -n 3
python3 .agents/skills/ui-ux-pro-max/scripts/search.py 'keyboard dragging alternative' --domain ux -n 2
python3 .agents/skills/ui-ux-pro-max/scripts/search.py 'async loading error' --stack react -n 2
```

The CSV contains **50 active styles**. Exact search returned `glassmorphism` with
`Status: active`, light/dark support, blur/layering recommendations and conditional
contrast/accessibility requirements. Product search returned Short Video Editor
and explicitly described a timeline-focused workspace. Glassmorphism is listed
among its secondary visual choices, consistent with the owner's preference.

The design-system query `video editor glassmorphism desktop`, followed by one
narrower `desktop video editor` retry, returned Hero-centric landing-page patterns
and OLED styling. Those results do not match this desktop-workspace task and were
not persisted as a master design system. The specification instead applies the
verified active style and relevant UX rules to the owner's intended layout.

The proposed glass treatment is intentionally limited to shell/overlay surfaces.
The generic opacity/motion examples are recommendations, not instructions to
sacrifice video clarity, timeline precision, keyboard access or contrast. No
network calls or paid APIs are used by these local CSV searches.
