#!/usr/bin/env python3
"""Builds the GitHub wiki from wiki/pages/ into wiki/_build/ (or the folder given with --out).

Pages are Markdown templates. Besides normal text they can contain directives, each on its own line:

  <!-- include: README.md -->                     the whole file (its # title is dropped)
  <!-- include: HANDOFF.md#Traps we already -->   one section: the heading that starts with this text,
                                                  down to the next heading of the same or higher level
  <!-- generate: config -->                       settings table from the three node sketches
  <!-- generate: milestones -->                   milestone progress, read from GitHub issues
  <!-- generate: sprint -->                       every story with its tasks, points and state
  <!-- generate: open-bugs -->                    open bugs and issues

Included text keeps one copy of everything: edit README, WIRING, HANDOFF or docs/AGILE.md and the wiki
follows. Relative links are rewritten to point at the repo (or at the wiki page that carries that file).

GitHub data comes from the REST API with GITHUB_TOKEN (set in Actions), or from `gh auth token` locally.
With neither, or with --offline, the generated GitHub sections say the data was not available.
--check fails on a missing include file or section, without needing GitHub.

  python3 wiki/build_wiki.py            # build into wiki/_build/
  python3 wiki/build_wiki.py --check    # what the pull-request check runs
"""
import argparse, json, os, re, subprocess, sys, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES = ROOT / "wiki" / "pages"
REPO = os.environ.get("GITHUB_REPOSITORY", "bash-y/mesh-barista")
BRANCH = "main"
BLOB = f"https://github.com/{REPO}/blob/{BRANCH}/"
# Repo files that have their own wiki page: links to them go to the page instead of the file.
FILE_PAGE = {"WIRING.md": "Hardware-and-Wiring", "docs/AGILE.md": "Development-Workflow",
             "HANDOFF.md": "Handoff"}
SKETCHES = [("Node 1 · Pump station", "node1_pump_station/node1_pump_station.ino"),
            ("Node 2 · Control center", "node2_control_center/node2_control_center.ino"),
            ("Node 3 · Output", "node3_output/node3_output.ino"),
            ("Mesh (all nodes)", "dashboard_src/barista_mesh.h")]

DIRECTIVE = re.compile(r"^<!--\s*(include|generate):\s*(.+?)\s*-->\s*$", re.M)
HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
LINK = re.compile(r"(!?\[[^\]]*\]\()([^)\s]+)(\))")
errors = []


# ---------- includes ----------
def rewrite_links(text, src):
    """Relative links in an included file become repo or wiki links."""
    def fix(m):
        url = m.group(2)
        if re.match(r"^[a-z]+:|^#|^/", url):
            return m.group(0)
        path, _, anchor = url.partition("#")
        target = os.path.normpath(os.path.join(src.parent.relative_to(ROOT), path)).replace(os.sep, "/")
        if target in FILE_PAGE and not m.group(1).startswith("!"):
            return f"{m.group(1)}{FILE_PAGE[target]}{'#' + anchor if anchor else ''}{m.group(3)}"
        if m.group(1).startswith("!"):  # images need the raw file, not GitHub's file page
            return f"{m.group(1)}https://github.com/{REPO}/raw/{BRANCH}/{target}{m.group(3)}"
        return f"{m.group(1)}{BLOB}{target}{'#' + anchor if anchor else ''}{m.group(3)}"
    return LINK.sub(fix, text)


def section(lines, title):
    """The lines of the section whose heading starts with `title`, heading included."""
    in_code, start, level = False, None, 0
    for i, line in enumerate(lines):
        if line.startswith("```"):
            in_code = not in_code
        m = None if in_code else HEADING.match(line)
        if start is None and m and m.group(2).strip().startswith(title):
            start, level = i, len(m.group(1))
        elif start is not None and m and len(m.group(1)) <= level:
            return lines[start:i]
    return lines[start:] if start is not None else None


def shift(lines, top):
    """Move headings so the shallowest one sits at level `top` (code blocks untouched)."""
    in_code, levels = False, []
    for l in lines:
        in_code ^= l.startswith("```")
        if not in_code and HEADING.match(l):
            levels.append(len(HEADING.match(l).group(1)))
    d = top - min(levels) if levels else 0
    out, in_code = [], False
    for l in lines:
        in_code ^= l.startswith("```")
        m = None if in_code else HEADING.match(l)
        out.append("#" * max(1, min(6, len(m.group(1)) + d)) + " " + m.group(2) if m else l)
    return out


def include(arg, top_level):
    file, _, title = arg.partition("#")
    src = ROOT / file
    if not src.exists():
        errors.append(f"include: no file {file}")
        return f"> **Missing:** `{file}`"
    lines = src.read_text().splitlines()
    if title:
        part = section(lines, title.strip())
        if part is None:
            errors.append(f"include: no section starting '{title}' in {file}")
            return f"> **Missing:** section `{title}` in `{file}`"
        lines = part
    elif lines and lines[0].startswith("# "):
        lines = lines[1:]  # the page has its own title
    body = "\n".join(shift(lines, top_level)).strip()
    return rewrite_links(body, src) + f"\n\n<sub>From [{file}]({BLOB}{file}). Edit it there, not here.</sub>"


# ---------- generated: settings from the sketches ----------
DECL = re.compile(r"^\s*(?:(?:static\s+)?const\s+[\w:*\s]+?\s\**\s*([A-Z][A-Z0-9_]*)(\[[^\]]*\])*\s*=\s*(.*?)(;|$)|#define\s+([A-Z][A-Z0-9_]*)\s+(.+?))\s*(?://\s*(.*))?$")


def gen_config(_gh):
    out = []
    for name, path in SKETCHES:
        rows = []
        for n, line in enumerate((ROOT / path).read_text().splitlines(), 1):
            if line.startswith((" ", "\t")):
                continue  # only top-level settings, not locals inside functions
            m = DECL.match(line)
            if not m:
                continue
            ident = m.group(1) or m.group(5)
            value = (m.group(3) if m.group(1) else m.group(6)).strip()
            if not m.group(4) and m.group(1):
                value += " …"  # continues on the next lines
            note = (m.group(7) or "").replace("|", "\\|")
            rows.append(f"| `{ident}` | `{value.replace('|', chr(92) + '|')}` | {note} | [{n}]({BLOB}{path}#L{n}) |")
        out.append(f"### {name}\n\n`{path}`\n\n| Setting | Value | Note | Line |\n| --- | --- | --- | --- |\n" + "\n".join(rows))
    return "\n\n".join(out)


# ---------- generated: from GitHub issues (UIW-PMD conventions) ----------
def token():
    if os.environ.get("GITHUB_TOKEN"):
        return os.environ["GITHUB_TOKEN"]
    try:
        return subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


class GitHub:
    def __init__(self, tok):
        self.tok, self._issues, self._ms = tok, None, None

    def get(self, path):
        out, url = [], f"https://api.github.com/repos/{REPO}/{path}"
        while url:
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {self.tok}",
                                                       "Accept": "application/vnd.github+json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                out += json.loads(r.read())
                nxt = re.search(r'<([^>]+)>;\s*rel="next"', r.headers.get("Link", ""))
                url = nxt.group(1) if nxt else None
        return out

    def issues(self):
        if self._issues is None:
            self._issues = [i for i in self.get("issues?state=all&per_page=100") if "pull_request" not in i]
        return self._issues

    def milestones(self):
        if self._ms is None:
            self._ms = sorted(self.get("milestones?state=all&per_page=100"), key=lambda m: m["due_on"] or "9")
        return self._ms


TYPES = [("User Story", ("user story", "story")), ("Bug", ("bug", "defect")), ("Sub-task", ("sub-task", "subtask", "sub-issue")),
         ("Task", ("task",)), ("Issue", ("issue",))]


def kind(i):
    t = i["title"].lower()
    for name, keys in TYPES:
        if any(t.startswith(k) for k in keys):
            return name
    labels = {l["name"].lower() for l in i["labels"]}
    for name, keys in TYPES:
        if labels & set(keys):
            return name
    return "Untracked"


def points(i):
    m = re.search(r"(?im)^\s*(?:story points|estimate)\s*:\s*(\d+(?:\.\d+)?)", i.get("body") or "")
    return float(m.group(1)) if m else None


def parent(i):
    m = re.search(r"(?im)^\s*(?:parent|part of|sub-task of)\s*:?\s*#(\d+)", i.get("body") or "")
    return int(m.group(1)) if m else None


fmt = lambda p: "–" if p is None else (f"{p:g}")
pts = lambda p: "– pts" if p is None else f"{p:g} pt" + ("" if p == 1 else "s")
state = lambda i: "✅" if i["state"] == "closed" else "⬜"
link = lambda i: f"[#{i['number']}]({i['html_url']})"
clean = lambda t: re.sub(r"^(user story|task|bug|issue|sub-task)\s*[-:]\s*", "", t, flags=re.I)
due = lambda m: datetime.fromisoformat(m["due_on"].replace("Z", "+00:00")).strftime("%b %d, %Y") if m["due_on"] else "TBD"


def story_points(story, issues):
    """PMD rule: an estimated story counts once for its tree; otherwise the sum of its children."""
    if points(story) is not None:
        return points(story)
    kids = [points(i) for i in issues if parent(i) == story["number"]]
    return sum(k for k in kids if k is not None) if any(k is not None for k in kids) else None


def gen_milestones(gh):
    issues = gh.issues()
    rows = []
    for m in gh.milestones():
        items = [i for i in issues if (i["milestone"] or {}).get("number") == m["number"]]
        stories = [i for i in items if kind(i) == "User Story"]
        total = sum(story_points(s, items) or 0 for s in stories)
        done = sum(story_points(s, items) or 0 for s in stories if s["state"] == "closed")
        closed = sum(i["state"] == "closed" for i in items)
        pct = round(100 * closed / len(items)) if items else 0
        bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
        rows.append(f"| [{m['title']}]({m['html_url']}) | {due(m)} | `{bar}` {pct}% | {closed} / {len(items)} | "
                    f"{fmt(done)} / {fmt(total)} | {(m['description'] or '').splitlines()[0] if m['description'] else ''} |")
    return ("| Milestone | Due | Progress (issues) | Issues closed | Story points done | Goal |\n"
            "| --- | --- | --- | --- | --- | --- |\n" + "\n".join(rows))


def gen_sprint(gh):
    issues = gh.issues()
    by_n = {i["number"]: i for i in issues}
    out = []
    for m in gh.milestones():
        items = [i for i in issues if (i["milestone"] or {}).get("number") == m["number"]]
        if not items:
            continue
        out.append(f"\n### {m['title']} · due {due(m)}")
        for s in sorted((i for i in items if kind(i) == "User Story"), key=lambda i: i["number"]):
            kids = sorted((i for i in items if parent(i) == s["number"]), key=lambda i: i["number"])
            done = sum(k["state"] == "closed" for k in kids)
            out.append(f"\n{state(s)} **{clean(s['title'])}** {link(s)} · {pts(story_points(s, items))} · "
                       f"{done}/{len(kids)} done" + (f" · {', '.join(a['login'] for a in s['assignees'])}" if s["assignees"] else " · *unassigned*"))
            for k in kids:
                who = ", ".join(a["login"] for a in k["assignees"]) or "unassigned"
                blocked = re.findall(r"(?im)^\s*(?:blocked by|depends on)\s*#(\d+)", k.get("body") or "")
                open_blockers = [b for b in blocked if int(b) in by_n and by_n[int(b)]["state"] == "open"]
                out.append(f"- {state(k)} {kind(k)}: {clean(k['title'])} {link(k)} · {pts(points(k))} · {who}"
                           + (f" · ⛔ blocked by {', '.join('#' + b for b in open_blockers)}" if open_blockers else ""))
        loose = [i for i in items if kind(i) != "User Story" and not parent(i)]
        if loose:
            out.append("\n**Not linked to a story**\n" + "\n".join(f"- {state(i)} {kind(i)}: {clean(i['title'])} {link(i)}" for i in loose))
    none = [i for i in issues if not i["milestone"]]
    if none:
        out.append("\n### No milestone\n" + "\n".join(f"- {state(i)} {kind(i)}: {clean(i['title'])} {link(i)}" for i in none))
    return "\n".join(out)


def gen_open_bugs(gh):
    rows = [i for i in gh.issues() if i["state"] == "open" and kind(i) in ("Bug", "Issue")]
    if not rows:
        return "No open bugs or issues."
    return "\n".join(f"- {kind(i)}: {clean(i['title'])} {link(i)}" for i in sorted(rows, key=lambda i: i["number"]))


GENERATORS = {"config": (gen_config, False), "milestones": (gen_milestones, True),
              "sprint": (gen_sprint, True), "open-bugs": (gen_open_bugs, True)}


# ---------- build ----------
def render(text, gh):
    lines, out = text.splitlines(), []
    level = 2  # an include sits under the page title, unless it follows a deeper heading
    for line in lines:
        m = DIRECTIVE.match(line)
        h = HEADING.match(line)
        if h:
            level = len(h.group(1)) + 1
        if not m:
            out.append(line)
        elif m.group(1) == "include":
            out.append(include(m.group(2), min(level, 6)))
        else:
            fn, needs_github = GENERATORS.get(m.group(2), (None, False))
            if fn is None:
                errors.append(f"generate: unknown '{m.group(2)}'")
                out.append(f"> **Unknown generator** `{m.group(2)}`")
            elif needs_github and gh is None:
                out.append("> *GitHub data not available in this build. It is filled in when the wiki is published.*")
            else:
                out.append(fn(gh))
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "wiki" / "_build"))
    ap.add_argument("--offline", action="store_true", help="skip GitHub API sections")
    ap.add_argument("--check", action="store_true", help="offline build that fails on broken includes")
    a = ap.parse_args()
    tok = None if (a.offline or a.check) else token()
    gh = GitHub(tok) if tok else None
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.md"):
        old.unlink()
    commit = os.environ.get("GITHUB_SHA") or subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                                                            capture_output=True, text=True).stdout.strip()
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    for page in sorted(PAGES.glob("*.md")):
        (out / page.name).write_text(render(page.read_text(), gh))
    (out / "_Footer.md").write_text(
        f"Built from [`{commit[:7]}`](https://github.com/{REPO}/commit/{commit}) on {stamp}. "
        f"This wiki is generated: edit [`wiki/pages/`](https://github.com/{REPO}/tree/{BRANCH}/wiki/pages) "
        f"or the files it includes, not these pages.\n")
    for e in errors:
        print("ERROR:", e, file=sys.stderr)
    print(f"{len(list(PAGES.glob('*.md')))} pages -> {out}" + ("" if gh else " (no GitHub data)"))
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
