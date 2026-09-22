# claude-skills

Global Claude Code skills, synced across machines via this repo.

## Setup on a new machine

```bash
git clone https://github.com/kingluminance/claude-skills.git ~/.claude/skills
```

## Two kinds of entries here

- **Hand-written / manually vendored skills** (e.g. `parallel-feature`, `archify`, `ponytail`, `find-skills`,
  `hwpxskill`, `claw-hwp`)
  — plain folders, fully tracked by this repo. `git pull` is enough to sync them.
  `hwpxskill` needs a local `.venv` with `lxml` (not tracked, recreate per machine:
  `python3 -m venv hwpxskill/.venv && hwpxskill/.venv/bin/pip install lxml`).
  `claw-hwp` vendors its Node deps under `scripts/vendor/`, so it needs only Node 18+.
- **Skills installed via `npx skills add ... -g`** (e.g. `cli-anything-gimp`)
  — the CLI stores the real files under `~/.agents/skills/<name>` and only
  symlinks `~/.claude/skills/<name>` to it. On a machine where git has real
  symlink support (`core.symlinks=true`, the default on macOS/Linux), that
  symlink is what gets committed — cloning on another machine expecting a
  symlink target will need `~/.agents/skills/<name>` to exist there too,
  which git alone won't provide. On this machine `core.symlinks=false`
  (typical on Windows), so git instead commits the dereferenced file
  contents — a plain, self-contained copy that `git pull` syncs correctly
  on any OS.
  Either way, the SKILL.md instructions sync fine. What does **not** sync
  automatically is the underlying tool the skill wraps — e.g.
  `cli-anything-gimp` needs `pip install cli-anything-gimp` run separately
  on each machine before the skill's commands actually work.
