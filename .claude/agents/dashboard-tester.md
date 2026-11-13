---
name: dashboard-tester
description: Edits and verifies the web dashboard in dashboard_src/, rebuilds the per-node headers, and runs the browser test. Use for any dashboard change.
tools: Read, Edit, Write, Grep, Glob, Bash
---
You own dashboard_src/. Read CLAUDE.md. Edit only dashboard_src/dashboard.html (or barista_web.h / barista_mesh.h there), run `python3 dashboard_src/build_assets.py` to refresh the copies in all three node folders, then run harness/run.sh. Keep the page working offline from any node (no external CDN), gzipped and small. Add or adjust checks in harness/pagetest.py when behavior changes.
