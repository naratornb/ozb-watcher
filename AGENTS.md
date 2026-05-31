# Agent guide — ozb-watcher

A small Python script + GitHub Action that watches OzBargain for new MacBook deals and notifies Discord + WhatsApp. See `README.md` for the deploy tutorial. This file tells coding agents how to do git in this repo.

## Branches

Format: `<type>/<short-kebab-description>` where `<type>` is a Conventional Commits type (`feat`, `fix`, `docs`, `chore`, `ci`, `refactor`, `test`, `perf`) and the description is 3–6 lowercase hyphenated words describing the *outcome*.

- Good: `feat/active-recent-filters`, `fix/avoid-cloudflare-block`
- **Never** push under an auto-generated agent slug (`claude/<random>`). Rename to the convention before pushing.
- Base branch is `main`.

## Commits

Conventional Commits, lowercase imperative subject under ~72 chars, no trailing period:

```
<type>: <subject>

<body — what changed and why; wrap at ~72 chars>

Co-Authored-By: Claude <model> <noreply@anthropic.com>
```

- One commit per **coherent topic**. Related code + README + tests in one commit is fine (e.g. `feat: filter to active deals posted within the last 30 days` bundled two flags + a README update). Unrelated changes don't hitch a ride.
- Body explains *why*, not *what*. Skip the body for trivial commits.
- Prefer **new commits** over `--amend` once pushed.

**Exception — workflow auto-commits:** the notifier workflow commits `seen.json` with the literal message `Update seen deals [skip ci]`. Don't change that string; the `[skip ci]` token prevents Actions from re-triggering.

## Push, but don't open the PR

The agent pushes the verified-complete branch and **stops**. It prints the GitHub compare URL from the push output so the user can click through to **New PR**. The agent does **not** run `gh pr create` unless the user explicitly asks. The user owns the PR's title, body, and the repo's PR record.

## PR titles and bodies (for when the user opens the PR — or when the agent is explicitly asked to)

**Title** mirrors the commit subject — same type, same lowercase imperative.

**Body format depends on the commit type:**

- `feat:` / `refactor:` → rich 5-section template (see PR #1):

  ```
  ## Summary                       — bullets, one per change
  ## Why                           — 1–3 sentences on the user-visible motivation
  ## Behaviour / compatibility     — what changes, what's backwards-compatible
  ## Verification                  — commands run, expected output, edge cases
  ## Reviewer notes                — assumptions, caveats, tradeoffs
  ```

- `fix:` / `docs:` / `chore:` / `ci:` → prose body, typically the commit body verbatim (see PR #3).

No `🤖 Generated with Claude Code` footer in PR bodies. (Commit `Co-Authored-By` lines are fine and match the repo's history.)

## Other rules

- Don't bypass hooks (`--no-verify`) or signing unless asked.
- Don't force-push to `main`. Force-pushing a feature branch is fine while no one's reviewing it.
- Agents don't merge PRs — wait for the user. The repo uses merge commits.
