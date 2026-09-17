---
name: parallel-feature
description: Develop several independent game features in parallel using subagents, handle shared-file conflict zones with one dedicated agent first, then merge and test automatically.
---

# /parallel-feature — Godot Parallel Feature Development Pipeline

When the user calls `/parallel-feature <feature1>, <feature2>, <feature3> ...`, execute the following stages in order. Do not move to the next stage until the current one is complete.

## Stage 0 — Setup

- Decide a branch name for each listed feature (e.g. `feature/npc-a`, `feature/npc-b`, `feature/inventory`).
- Confirm the current git working tree is clean. If there are uncommitted changes, notify the user before proceeding.

## Stage 1 — Parallel Planning (no code yet)

Spawn one subagent per feature, in parallel. Instruct each subagent as follows:

> Produce a plan only. Do not write any code yet.
> Report:
> - New scene (.tscn) and script (.gd) files you expect to create
> - Existing files you expect to modify (especially autoloads/singletons, player.gd, game_manager-type scripts, global signal buses, and project.godot)
> - Any files you think will overlap with other features

Because of how Godot projects are structured, always treat the following as conflict candidates and require every subagent to mention them explicitly if touched:
- Any autoload script (anything registered under the `[autoload]` section of project.godot)
- Shared signal buses or global game-state management scripts
- The player script (especially relevant if the feature involves inventory or interaction)
- The main scene or root UI scene
- project.godot itself (input map, layer settings, etc.)

## Stage 2 — Consolidate Conflict Zones

Compare the plans from Stage 1 and extract the overlapping files. Report to the human in this format and wait for confirmation:

```
Conflict candidates:
- [file]: needed by [feature A] for X, needed by [feature B] for Y
...
Proceed as-is, or revise the list?
```

**Do not proceed to Stage 3 without this confirmation.**

## Stage 3 — Dedicated Development of Conflict Zones

- Create a separate branch (`feature/shared-interfaces`).
- Spawn a single subagent to implement only the conflict files confirmed in Stage 2. Instruct it to design an interface that satisfies every feature's stated needs.
- Once done, commit, and output a clear list of the functions/signals added or changed (e.g. `Player.add_item(item_id: String) -> void`, `signal item_added(item_id)`).
- Show this interface list to the human and get approval. **Do not proceed without this approval either.**

## Stage 4 — Parallel Implementation

- Create a separate git worktree per feature (e.g. `git worktree add ../worktree-npc-a feature/npc-a`), branching each from `feature/shared-interfaces` created in Stage 3.
- Run one subagent per worktree, in parallel, explicitly stating the interfaces confirmed in Stage 3 in the prompt: "Assume the following functions/signals are already implemented, and build against them."
- Each subagent must not touch files outside its own worktree folder.
- Commit to each feature branch once done.

## Stage 5 — Merge

- Merge `feature/shared-interfaces` into the main branch first.
- Then merge each feature branch in turn. If conflicts occur in `.tscn`/`.tres` files, merge carefully with awareness of Godot's scene file format (UIDs, node tree structure); if automatic resolution is ambiguous, report it to the human instead of guessing.
- After merging, verify that project.godot is valid and there are no duplicate scene UIDs.

## Stage 6 — Test

- Verify the project runs cleanly in Godot headless mode (e.g. `godot --headless --quit` to catch parse errors).
- Run unit tests if any exist.
- Confirm each feature is actually wired to the interface it was told to assume (e.g. check that the inventory system genuinely subscribes to the `item_added` signal).
- If something fails, report exactly which branch/file caused it, and which branch needs to be revisited.

## Final Report

Once all stages are complete, summarize:
- List of merged branches
- List of newly created files
- Test results
- Remaining issues or anything the human should manually verify
