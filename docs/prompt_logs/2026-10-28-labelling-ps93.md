# 2026-10-28 — Subtopic scheme and annotator A labels for PS 93/26

## 1. Subtopic scheme

**Request:** "Could we take a look at the labels together" — review the team's subtopic scheme
for PS 93/26 (*Kjernekraft – naturvirkninger*) before labelling.

**Agent output (trimmed):** pointed out that the theme covers only part of the item (the
competence programme and the county's role have no subtopic), listed overlaps
(*Radioaktivt avfall* vs. *Strålevern og utslipp*, *Arealbruk* vs. *Følgeinngrep*), and proposed
a rewritten scheme with boundary rules.

**Kept / corrected / rejected:**
- Kept: scope limited to natural effects (gold only if a subtopic fits); "tag all that fit";
  boundary rules in the guideline; tags used only on PS 93/26.
- Corrected by the team: the scheme moved from `docs/labels.txt` to `docs/labels.yaml`;
  noise (*støy*) and ports (*havner*) added; accident risk placed under
  *Strålevern, utslipp og ulykker* when it concerns consequences for nature and people.
- Corrected by the team: the PS 93/26 agenda description now names the theme
  ("med vekt på naturvirkninger av kjernekraft") but not the subtopics, so the pipeline is not
  given the checklist.
- Deferred: a guard in `label.py` enforcing the tag rules; the written rule is tried first.

## 2. Annotator A labels (agent-drafted, human-confirmed)

**Request:** "Try and find the fitting paragraphs and I can confirm them."

**Agent output (trimmed):** before drafting, the agent flagged that agent-drafted gold for a
pipeline the agent also builds is a bias risk; the team chose to proceed with the file marked
*agent-drafted, human-confirmed*. The agent searched the case paper (pp. 3–7) and NOU 2026:4
(pp. 8–501), mainly chapters 2.3, 6, 11.1.4, 11.3.4, 12, 23.3 and 29.3, and proposed
52 candidates in four batches, each with page, section, tags, quote and a keep/drop view.
Every quote was dry-run against `label.py`'s verbatim check before it was shown.

**Kept / corrected / rejected:**
- Kept 40, dropped 12 (annotator A accepted the agent's view on every row). Dropped because
  they overlapped a kept passage (e.g. C2, C4, C11, S4, L4), were not a local nature effect
  (N4 uranium mining abroad, V6 French heatwave shutdowns), or were about governance or
  technical requirements rather than nature (R7, F5, F6). A5 was marked "optional" and left out.
- Coverage: every subtopic has ≥ 4 passages; *Følgeinngrep* and *Landskap og friluftsliv*
  are thin because the NOU says little about power lines or the plant's visual impact.

## 3. PS 94–98/26 and provisional gold

**Request:** "Could we do 4 and 5 with only the A variant and add a reminder to do the B variant
and compare."

**Agent output (trimmed):** pointed out that step 2 (annotator B) cannot be done by the agent
without making agreement meaningless, and that the harness only scores items present in the
labels file. Drafted PS 94–98/26 the same way (case paper first; PS 97/26 with targeted
cross-references, `via: cross_reference`, after the user chose option b over "case paper only"
or "all 520 pages"), then copied A to the gold path as provisional gold and started `eval-live`.

**Kept / corrected / rejected:** annotator A accepted the agent's view on every row: 43 kept,
7 dropped (overlaps such as O7, G8, I10, F10; process details such as G9; minor changes such as
I8; and T6, an application letter line that also contains names). The user corrected the
agent's wording "planning documents" for PS 97/26 by asking what was meant; the agent explained
it was the municipal sub-plan's attachments, not a plantation.

## 4. Note: early run without labels

Before this session the harness ran the real meeting once while no labels existed (replay,
0 model calls, no selections). Nobody looked at the output and the run was deleted; the harness
now skips unlabelled cases. The labels above were drafted without seeing any system output for
this meeting.
