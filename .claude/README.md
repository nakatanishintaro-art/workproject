# Superpowers skills (repo-local install)

This directory installs the [**superpowers**](https://github.com/obra/superpowers)
skills library into the project so it is available in Claude Code on the web
(where the interactive `/plugin install` command is not available).

- **Source:** https://github.com/obra/superpowers
- **Version:** 6.1.1
- **Author:** Jesse Vincent
- **License:** MIT (see `SUPERPOWERS-LICENSE`)

## What's here

- `skills/` — the 14 superpowers skills (TDD, systematic debugging, brainstorming,
  writing/executing plans, code review, git worktrees, etc.). Claude discovers
  these automatically and invokes them via the `Skill` tool.
- `hooks/superpowers-session-start` — a `SessionStart` hook that injects the
  `using-superpowers` skill at the start of each session so Claude reaches for
  the relevant skill before acting.
- `settings.json` — wires the `SessionStart` hook.

## Updating

Re-clone the upstream repo and copy `skills/*` over `skills/` here, then bump
the version above:

```bash
git clone --depth 1 https://github.com/obra/superpowers /tmp/superpowers
cp -R /tmp/superpowers/skills/* .claude/skills/
```
