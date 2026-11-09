---
name: release
description: Cut a release from dev. Bumps the version on dev, runs the full gate, commits, fast-forwards main to dev, and tags main, then pushes so the release workflow publishes to PyPI. User-invoked only.
argument-hint: major | minor | patch
disable-model-invocation: true
---

Release bump: $ARGUMENTS

Branch model: `main` holds releases only, `dev` accumulates squash-merged
feature PRs, and a release is `dev` fast-forwarded into `main` plus a tag.

1. Preconditions; stop if any fails. `$ARGUMENTS` is `major`, `minor`, or
   `patch`. The tree is clean. The current branch is `dev`. If a remote
   exists, `git fetch` succeeds and `dev` is not behind `origin/dev`.
   `git log dev..main` is empty: `main` has nothing `dev` lacks. Otherwise
   the user merges `main` into `dev` first.
   First release: if `git tag -l "v$(uv version --short)"` is empty (the
   current version was never tagged) and `CHANGELOG.md` has an
   `## [Unreleased]` section to promote, `$ARGUMENTS` is not needed. Skip
   the bump in step 2 and release the current version.
2. Bump (skip on a first release): `uv run nox -s bump -- $ARGUMENTS`. Show
   the diff and
   the new version from `uv version --short`. In `CHANGELOG.md`, rename the
   `[Unreleased]` heading to the new version with today's date and add an
   empty `[Unreleased]` heading above it. On a first release, do this too
   unless the changelog already has a dated heading for the version.
3. Gate after the bump: `uv run nox`. Nothing is released from a failing
   tree, and the version test must see the new version.
4. Commit on `dev`: `git commit -am "chore(release): v$(uv version --short)"`.
5. Fast-forward `main` and tag it. The tag is annotated so `--follow-tags`
   pushes it:

       git switch main
       git merge --ff-only dev
       git tag -a "v$(uv version --short)" -m "v$(uv version --short)"
       git switch dev

6. Confirm with the user, then `git push origin dev main --follow-tags`. The
   tag runs `.github/workflows/release.yml`, which checks that the tag is on
   `main` and matches the project version, runs the CI gate, then publishes
   with trusted publishing.
