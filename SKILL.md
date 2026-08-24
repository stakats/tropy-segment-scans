---
name: tropy-segment-scans
description: Split a batch-scanned Tropy item into document-level items. Use whenever you ask to "split" a Tropy dossier/batch item, break a folder of archive photos into separate documents (letters, memoranda, mémoires), or merge a batch of Tropy photos into discrete items. Works through Tropy's local API against the open project.
allowed-tools: Bash(python3:*) Read
---

# Tropy Segment Scans

Turns one "whole dossier" Tropy item — dozens or hundreds of photos of an
archive folder — into document-level items, with metadata inherited from the
dossier, per-document metadata read off the page, and transcriptions for
handwritten material.

Photos are **moved**, not copied: the workflow explodes them out of the batch
item and merges them back into document groups, so no photo record is
duplicated and every change lands in Tropy's undo history.

> **Conventions are adaptable defaults.** The `for review` tag, the
> "empty dossier shell" rule, the descriptive-title convention and the
> diplomatic transcription style reflect one archival workflow. Adjust the
> prose here and the constants in `scripts/tsegment.py` to match your own.

## Prerequisites

- **Tropy's local API must be enabled** and the target project open.
  Default port 2019 (2029 on beta/dev channels); override with `--port`.
- **The `explode`, `merge` and `nav` routes must exist.** They are not yet in
  released Tropy — they come from
  [tropy#985](https://github.com/tropy/tropy/pull/985). Without them `execute`
  cannot move photos and will fail on the explode step.

## Hard rules

- **Never write to the `.tpy` file directly.** Every change goes through the
  local API so it stays in Tropy's undo history and in sync with the UI.
- **Never delete the batch item.** Once its photos are moved out it remains as
  an **empty dossier shell**, keeping the dossier-level metadata, tags and
  lists. That shell is the record of the folder as a physical unit.
- All new items get the **`for review`** tag (on top of the tags they inherit).
- Segment documents from the **images**, not from any existing transcription.

## Workflow

### 1. Locate

```bash
python3 ~/.claude/skills/tropy-segment-scans/scripts/tsegment.py locate <ITEM ID>
# or, acting on whatever is selected in Tropy:
python3 ~/.claude/skills/tropy-segment-scans/scripts/tsegment.py locate --selection
```

Resolves the batch item and downloads every photo as a rendered JPEG (rotation,
mirroring and adjustments applied — what Tropy *displays*, not the raw file),
in two renditions, to `/tmp/tropy-segment/<itemId>/`:

- `scan/page-001.jpg` … downscaled to 1024px on the long edge — for pass 1
- `full/page-001.jpg` … the full rendering — for pass 2
- `batch.json` — photo ids, filenames, dimensions, both image paths, the
  dossier's inherited metadata, and the pass-1 window plan
- `manifest.template.json`

### 2. Inspect in two passes

Reading every page closely is wasted effort: most photos only have to answer
"does a new document start here?". So the inspection is split.

**Pass 1 — boundaries, over `scan/`.** Read the downscaled images of *every*
photo and decide only where documents begin and end — see
[Finding document boundaries](#finding-document-boundaries) below. Do not read
the text for meaning; you are looking for discontinuity, which is exactly what
survives downscaling.

For a large dossier this still won't fit one context — `batch.json` gives
overlapping windows of ~25 photos (3 photos of overlap). Work through them in
order; when a document is still open at the end of a window, close it in the
next one rather than guessing.

**Pass 2 — metadata, over `full/`.** For each document found in pass 1, read
the full-resolution image of its **first and last page** (in these letters the
date and signature are as often at the end as the beginning). Extract title,
creator, date and type. Only these pages need full resolution, so a 40-document
dossier costs ~80 close reads rather than 189.

**Do not transcribe unless asked.** Segmenting is the default job; Tropy has
its own transcription (Transkribus via mino), and it is better at handwriting
than reading it off these images. Only when the researcher explicitly asks for
transcriptions do you produce them, from the `full/` images — see
[Transcription](#transcription).

#### Finding document boundaries

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

#### Capture unit

Establish from the first few photos whether a photo holds **one leaf**, an
**opening** (two pages at once), or a **recto/verso pair**, and apply that
consistently. Getting it wrong doubles or halves every document in the dossier.

#### Conventions

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

### 3. Write the manifest

Write `manifest.json` in the workdir. `photos` holds **photo ids** (from
`batch.json`), not page numbers:

```json
{
  "item": 1069,
  "documents": [
    {
      "photos": [1070, 1072],
      "title": "Bourgeat à la Société royale de médecine",
      "creator": "Bourgeat, Joseph",
      "date": "1759-03-12",
      "type": "Correspondence",
      "transcriptions": {
        "1070": "Monsieur, j'ay l'honneur de vous adresser le mémoire cy joint…"
      }
    }
  ]
}
```

Metadata rules:

- **Inherited automatically — never put these in the manifest.** The new items
  are duplicates of the batch item, so they already carry its identifier,
  archive, relation, source, rights, template, tags and lists.
- **`title`** is descriptive and document-specific
  (`"Bourgeat à la Société royale de médecine"`,
  `"Mémoire sur les fièvres de Saint-Domingue"`), with the correspondent in
  `creator`. Do not reuse the dossier's author-name title.
- **`date`** as written on the document, ISO when a full date is legible. It is
  written as a Tropy date, so ranges like `1777-1778` parse correctly.
- **`type`** — `Correspondence` for letters and memoranda sent as letters,
  `Memorandum` for *mémoires*, otherwise what the document is.
- **`transcriptions`** maps a photo id to its text. Only for handwritten pages.

### 4. Execute

```bash
python3 ~/.claude/skills/tropy-segment-scans/scripts/tsegment.py execute \
  /tmp/tropy-segment/<itemId>/manifest.json --dry-run   # check first
python3 ~/.claude/skills/tropy-segment-scans/scripts/tsegment.py execute \
  /tmp/tropy-segment/<itemId>/manifest.json
```

Validates the manifest against the live item (unknown photo ids and photos
assigned twice are fatal; unassigned photos only warn and stay on the shell),
then explodes the photos out, merges each document's photos into one item,
writes the per-document metadata, attaches transcriptions, applies `for review`,
and verifies each new item's photo list.

If a single document covers every photo, the batch item is updated in place
instead — no point shuffling photos into an identical new item.

### 5. Report

Tell the researcher: items created (ids + titles from `results.json`), any
unassigned photos left on the shell, transcriptions attached, and that
everything is tagged `for review`. On a Tropy without
[#984](https://github.com/tropy/tropy/pull/984), add that transcriptions will
not show up until the project is reopened (see below).

## Transcription

**Opt-in.** By default this skill segments and catalogues only, leaving the
`transcriptions` key out of the manifest entirely. Tropy transcribes through
Transkribus, which is purpose-built for handwriting; duplicating that here
costs a full-resolution read of every page to produce a second-best result.

When the researcher does ask for transcriptions, they are read from the
**image** and land in Tropy's native transcription store (not a note), so they
sit where Tropy's own transcription feature puts them.

To guarantee segmentation only regardless of what a manifest contains, pass
`--no-transcriptions` to `execute`.

Editorial convention — **diplomatic, with uncertainty marked**:

- Keep original spelling, accentuation and capitalisation (`j'ay`, `cy joint`,
  `isle`). Do not modernise.
- Preserve the original line breaks.
- **Never silently invent a reading.** Mark a doubtful word `[cette isle?]` and
  an unreadable one `[illisible]`. With cursive this is the failure mode that
  matters: a fluent guess is worse than a marked gap, because it cannot be
  distinguished from a real reading later.

## Gotchas

- **Transcriptions need [#984](https://github.com/tropy/tropy/pull/984) to show
  up straight away.** Before that fix, `POST /transcriptions` wrote to the
  database without updating application state, so neither the UI nor the API
  saw a new transcription until the project reloaded. The data was always
  there — on an older build, verify with the DB rather than a read-back.
- **Do not read back merged-away items.** After a merge, `GET /items/:id` on a
  merged-away item still reports its old photos and `deleted:false`, though the
  database has it correctly trashed. Trust the merge response.
- **The project must be open in Tropy.** The API resolves `current` to the
  focused project window; with nothing open every route returns
  `404 no project is open`.
- **`locate --selection` needs exactly one item selected** in the project view.
  Tropy tracks one current photo, not a multi-photo selection, so the selection
  addresses items.
- Large dossiers are slow to fetch — one rendered JPEG per photo, downscaled
  locally afterwards. `locate` is read-only and safe to re-run.
- Downscaling uses Pillow if installed, otherwise `sips` on macOS. With neither,
  `locate` warns and pass 1 falls back to the full renderings — correct, just
  more to look at. Override the size with `--scan-edge`.
