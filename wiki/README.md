# The wiki source

The [project wiki](https://github.com/bash-y/mesh-barista/wiki) is generated from this folder. Do not
edit pages on the wiki website: the next publish overwrites them.

## How the wiki is built

- **Pages** are Markdown files in `wiki/pages/`. The file name is the page name (`Safety-Logic.md` is the
  *Safety Logic* page); `_Sidebar.md` is the menu. Link between pages with `[[Page Name]]`.
- **Includes keep one copy of everything.** A line like `<!-- include: HANDOFF.md#Traps we already -->`
  pulls in that section of the repo file (the heading that starts with that text, down to the next
  heading of the same level). `<!-- include: WIRING.md -->` pulls in the whole file. So README, WIRING,
  HANDOFF and docs/AGILE.md stay the source, and the wiki follows them.
- **Generated sections** are filled in on every build:
  - `<!-- generate: config -->`: every setting in the three sketches and the mesh code, with line links.
  - `<!-- generate: milestones -->`, `sprint`, `open-bugs`: progress read from the GitHub issues, using
    the UIW-PMD conventions (type, `Parent: #N`, `Story points: N`, `Blocked by #N`).
- **Publishing is automatic.** The *Wiki* GitHub Action (`.github/workflows/wiki.yml`) rebuilds and pushes
  the wiki when `main` changes, when an issue or milestone changes, every morning, and on demand
  (Actions → Wiki → Run workflow). On a pull request it only checks that every include still resolves,
  so renaming a heading that the wiki uses fails the check instead of silently emptying a page.

To add a page: create `wiki/pages/New-Page.md`, add it to `_Sidebar.md`, and link it from `Home.md`.

To preview locally:

```sh
python3 wiki/build_wiki.py            # writes wiki/_build/ (reads GitHub through `gh` if logged in)
python3 wiki/build_wiki.py --check    # the pull-request check
```
