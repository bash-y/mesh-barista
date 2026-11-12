# How we track the work

Mesh Barista is planned in 2-week sprints on GitHub and tracked with the
[UIW-PMD dashboard](https://github.com/UIWCyber/UIW-PMD). The dashboard is read-only: everything it
shows comes from the issues, milestones and project board here, so **the issues are the plan**. Follow
the conventions below and the Gantt, board, burndown and workload charts stay correct.

- **Board:** the "Mesh Barista" GitHub Project, linked to this repo (Projects tab).
- **Sprint 1 starts:** Mon Nov 16, 2026. Sprint 2: Nov 30 to Dec 13.
- **Team:** Sebastian Cadena, Daniel Critchlow Jr.

## How the work is broken down

The dashboard shows one hierarchy: **Milestone → User Stories → Tasks / Issues → Sub-tasks / Bugs**.

| Level | What it is here | Example |
| --- | --- | --- |
| Milestone | A deliverable with a due date. The due date puts its work in a sprint. | *Reliable hardware*, due Nov 29 |
| User Story | Something a user needs, with acceptance criteria. | *User Story - Every pour is based on a measured flow rate* |
| Task / Issue | One piece of work toward a story, a day or two at most. | *Task: Measure each pump's flow rate* |
| Sub-task / Bug | A small step inside a task, or a defect. | *Bug: A relayed mesh message can be processed twice* |

Current milestones:

| Milestone | Due | Sprint | Goal |
| --- | --- | --- | --- |
| Reliable hardware | Nov 29 | 1 | Node 1 survives the cream pump, sensors stop drifting, the order queue works on real hardware, firmware weak spots fixed |
| Measured accuracy | Dec 6 | 2 | Measured flow rates and pour error, ruler-calibrated sensors, docs match the hardware |
| Next-version design | Dec 13 | 2 | Dr. Okan's feedback: accuracy across liquids, materials and pumps, load cell plan, accessory direction |

## Rules for every issue

These are the UIW-PMD conventions. The issue templates (**New issue** → pick a type) fill them in.

1. **Say what type it is.** Start the title with `User Story - `, `Task: `, `Issue - `, `Bug: ` or
   `Sub-task: `, and add the matching label (`user story`, `task`, `issue`, `bug`, `sub-task`). An item
   with no type shows as **Untracked** and sorts last.
2. **Put it in a milestone.** Without one it lands under **No milestone** at the bottom of the timeline.
3. **Link it to its parent.** Add tasks as **sub-issues** of their story (issue sidebar → *Create
   sub-issue* or *Add existing issue*), and also write `Parent: #7` in the task's description. Parent and
   child must be in the same milestone. A task that is not linked shows under **Not linked to a story**.
4. **Estimate it in story points.** Write `Story points: 3` under *Estimation of effort* in the
   description, and set the same number in the board's **Story Points** field. Use 1, 2, 3, 5 or 8;
   anything bigger is a story that needs splitting. Unestimated items show **–**.
   - A story's estimate covers its tasks, so the dashboard does not add them again. Keep a story's points
     equal to the sum of its tasks.
5. **Mark blockers.** Write `Blocked by #12` (or `Depends on #12`) in the description.
6. **Put it on the board.** In the issue sidebar, **Projects → Mesh Barista**, then set its **Status**,
   **Story Points** and **Sprint**.

## Board columns

| Status | Means | Who moves it |
| --- | --- | --- |
| Backlog | Not planned into a sprint yet | Sprint planning |
| Ready | Meets the Definition of Ready, planned for this sprint | Sprint planning |
| In Progress | Someone is working on it: assign yourself when you move it here | Whoever picks it up |
| In Review | A pull request is open, or a measurement is waiting for a teammate to check | The person who did the work |
| Done | Meets the Definition of Done, issue closed | Closing the issue or merging its PR (automatic) |

Keep work in progress small: one or two cards **In Progress** per person.

### Definition of Ready

A story can move to **Ready** when it has a **milestone**, an **assignee**, **acceptance criteria**, an
**estimate**, and its tasks are created as sub-issues. Clear any `Blocked by` first.

### Definition of Done

- Every acceptance criterion is checked off.
- Code changes are merged into `main` through a pull request that says `Closes #N`.
- Firmware changes are flashed and checked on the real nodes (see `HANDOFF.md`, "How to work on the
  hardware"); say which nodes in the PR.
- Measurements are recorded in a comment on the issue (raw numbers, not just the result).
- `README.md`, `WIRING.md` or `HANDOFF.md` are updated if the change affects them.

## The sprint

| When | What | Time |
| --- | --- | --- |
| First Monday | **Sprint planning:** pick stories from Backlog for the sprint goal, check each meets the Definition of Ready, set assignees, move to **Ready** | 30 min |
| Every class day or by message | **Stand-up:** what I did, what I'll do, what blocks me. Open the dashboard's **Activity → Recent activity** (24 hours) first | 10 min |
| Last Friday | **Sprint review:** demo what is Done on the hardware; unfinished work goes back to Backlog or the next sprint | 20 min |
| Last Friday | **Retrospective:** what to keep, what to change; add one improvement as an issue | 15 min |

## Branches and pull requests

- Branch from `main` for every task: `task/42-flow-rate`, `bug/45-mesh-duplicates`.
- Mention the issue in commits (`Measure pump flow rates (#42)`) so the work shows on the issue.
- Open a pull request that says `Closes #42`; the other teammate reviews it. Merging closes the issue and
  moves the card to Done.
- Never commit Wi-Fi passwords (`MESH_SSID` / `MESH_PASSWORD` stay placeholders).

## Tracking it on the UIW-PMD dashboard

1. Open `git_project-dashboard.html` from [UIW-PMD](https://github.com/UIWCyber/UIW-PMD) in a browser.
2. **••• → Connect a project…** and fill in:
   - **Project link:** `https://github.com/bash-y/mesh-barista`
   - **Sprint 1 starts on:** `2026-11-16`
   - **Access token:** to read the board's **Story Points** field and **Status** column, use a classic
     token with **repo** and **read:project** (the board belongs to a user, not an organization). A
     fine-grained token with Contents, Issues and Pull requests set to read-only works too, but then the
     dashboard shows only open or closed for status and reads points from the `Story points:` line in
     each issue.
3. Use it like the PMD README says:
   - **Daily:** Recent activity and the Board.
   - **Each sprint:** Burndown against the ideal line; Velocity compared with the last sprint.
   - **Each milestone:** the Gantt at the *User Stories* outline level; look for blocked and unlinked items.
   - **Team health:** Workload by member, so the work is split fairly. This needs every item assigned.
