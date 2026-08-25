# Segmentation policy

**This file is the segmentation policy, and nothing else depends on its
wording.** It governs one decision — where one document ends and the next
begins — and is meant to be revised on its own, per collection or as
experience accumulates, without touching the workflow in `SKILL.md` or the
client in `scripts/tsegment.py`.

The numeric settings that go with it live in `segmentation.json`.

Read this before pass 1.

## Finding document boundaries

**Continuity is the default.** Consecutive photos belong to the same document
unless something positively says otherwise. You are looking for
*discontinuity*, not reading for meaning — which is why this works downscaled,
and why it works the same way for a printed circular and a manuscript letter.

Ask three questions of each photo. Any one of them alone is weak; **when two
agree, call a boundary**.

**1. Does this page open something?**

- A heading, title block, letterhead, masthead or printed form header
- A salutation, address block or dateline set apart above the main text
- Text starting unusually low, leaving a deep top margin
- A centred title, a decorated or enlarged initial, a docket title

**2. Did the previous page close something?**

- Text stopping partway down, leaving blank space to the foot
- A signature, subscription, seal, stamp or set of initials at the foot
- A last line that ends cleanly rather than running to the edge
- A blank or near-blank page, or a page carrying only an endorsement or
  address panel

**3. Is the material different?**

- Change of hand, ink colour or writing implement (manuscript)
- Change of typeface, type size, column count or press quality (print)
- Change of paper: size, tone, edge, texture, ruling, watermark
- Change in the photograph itself — background, lighting, camera distance,
  orientation. The camera often registers a new physical object before the
  content does.

**Signals that a document continues.** These outrank a weak opening cue:

- Text running to the bottom edge, breaking mid-sentence or mid-word
- A catchword at the foot repeating the next page's first word
- Page or folio numbers continuing in sequence
- Same hand, ink, paper and layout as the page before

Numbering is worth special attention because it is legible when nothing else
is: foliation restarting, or a change of archival stamp, call number or
docket, is strong evidence of a new unit; numbers running on are strong
evidence against one.

## Capture unit

Establish from the first few photos whether a photo holds **one leaf**, an
**opening** (two pages at once), or a **recto/verso pair**, and apply that
consistently. Getting it wrong doubles or halves every document in the dossier.

## Conventions

- A **blank or near-blank page belongs to the document before it**, not the one
  after.
- **Covers, labels, rulers, colour targets and folder shots are not documents.**
  Leave them unassigned — they stay on the dossier shell.
- **Enclosures** — an attachment travelling with a covering document — are a
  judgement call: keep them with the parent when the parent refers to them and
  they carry no independent identity; make them their own item when they are
  substantial and separately titled.
- **When the evidence is ambiguous, join rather than split**, and say so in the
  report. An item holding two documents still shows them whole and in order,
  and is easy to split further; two items each holding half a document carry
  wrong metadata and read as complete. Everything is tagged `for review`
  regardless.
- A photo can hold the **end of one document and the start of another** —
  common in bound registers, rare in loose material. The manifest cannot split
  a photo: assign it to whichever document occupies most of it and flag it.
- If a document is **still open at the last photo**, it runs past the end of
  this item. Do not invent an ending — group what is there and report it.

## Collection-specific cues

Everything above is deliberately generic: it should read the same way for a
printed circular and a manuscript letter, in any archive. Cues that hold only
for a particular collection belong here, and are additive — they can raise
confidence in a boundary but should not override the continuation signals
above.

*Nothing recorded yet.* Observations awaiting promotion are in `NOTES.md`.
