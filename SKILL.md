---
name: tropy-segment-scans
description: Segment a batch-scanned Tropy item into document-level items. Use whenever you ask to "segment" or "split" a Tropy dossier/batch item, break a folder of archive photos into separate documents (letters, memoranda, mémoires), or merge a batch of Tropy photos into discrete items. Segmentation only -- Tropy transcribes via Transkribus. Works through Tropy's local API against the open project.
allowed-tools: Bash(python3:*) Read
---

# Tropy Segment Scans

Turns one "whole dossier" Tropy item — dozens or hundreds of photos of an
archive folder — into document-level items, with metadata inherited from the
dossier and per-document metadata read off the page.

**Segmentation only.** Do not transcribe; Tropy does that through Transkribus.

Photos are **moved**, not copied: the workflow explodes them out of the batch
item and merges them back into document groups, so no photo record is
duplicated and every change lands in Tropy's undo history.

> **Conventions are adaptable defaults.** The `for review` tag, the
> "empty dossier shell" rule and the descriptive-title convention reflect one
> archival workflow. The boundary rules and their settings are kept apart, in
> `segmentation.md` and `segmentation.json`, so they can be revised on their
> own.

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

The researcher asks once — "segment the selected item" — and you run all four
steps, pausing only to have the boundaries confirmed before anything is
written. Do not make them drive the steps by hand.

### 1. Locate

```bash
python3 ~/.claude/skills/tropy-segment-scans/scripts/tsegment.py locate <ITEM ID>
# or, acting on whatever is selected in Tropy:
python3 ~/.claude/skills/tropy-segment-scans/scripts/tsegment.py locate --selection
```

Resolves the batch item and downloads every photo as a rendered JPEG (rotation,
mirroring and adjustments applied — what Tropy *displays*, not the raw file),
in two renditions, to `/tmp/tropy-segment/<itemId>/`:

- `scan/page-001.jpg` … downscaled (`scan_edge`) — for pass 1
- `full/page-001.jpg` … the full rendering — for pass 2
- `batch.json` — photo ids, filenames, dimensions, both image paths, the
  dossier's inherited metadata, and the pass-1 window plan
- `manifest.template.json`

### 2. Inspect in two passes

Reading every page closely is wasted effort: most photos only have to answer
"does a new document start here?". So the inspection is split.

**Pass 1 — boundaries, over `scan/`.** Read the downscaled images of *every*
photo and decide only where documents begin and end, following
`segmentation.md`. Do not read the text for meaning; you are looking for
discontinuity, which is exactly what survives downscaling.

For a large dossier this still won't fit one context — `batch.json` gives
overlapping windows (`window`, `overlap`). Work through them in order; when a
document is still open at the end of a window, close it in the next one rather
than guessing.

**Pass 2 — metadata, over `full/`.** For each document found in pass 1, read
the full-resolution image of its **first and last page** (in these letters the
date and signature are as often at the end as the beginning). Extract title,
creator, date and type. Only these pages need full resolution, so a 40-document
dossier costs ~80 close reads rather than 189.

**Do not transcribe.** That is not this skill's job — see
[Transcription](#transcription).

#### Where the boundary rules live

The policy for this decision is in **`segmentation.md`**, and its settings in
**`segmentation.json`**. Read `segmentation.md` before pass 1. Both are meant
to be revised on their own — per collection, or as experience accumulates —
without touching this file or the script, so do not restate their rules here.

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
unassigned photos left on the shell, any boundary you were unsure of, and that
everything is tagged `for review`. Then point them at Tropy's transcription for
the new items — until those are transcribed, they carry no searchable text.

## Transcription

**Not this skill's job.** Leave the `transcriptions` key out of the manifest.
Tropy transcribes through Transkribus, which is purpose-built for handwriting;
doing it here would mean a full-resolution read of every page for a second-best
result. `execute` ignores transcriptions unless `--transcriptions` is passed.

Say so when reporting: segmenting gives correctly catalogued items, but a Tropy
photo carries no text layer, so until they are transcribed the new items have
no searchable text. Point the researcher at Tropy's transcription as the next
step.

If the researcher explicitly asks you to transcribe anyway, read from the
`full/` images, put the text on the document's `transcriptions` map keyed by
photo id, run `execute --transcriptions`, and follow a **diplomatic**
convention with uncertainty marked:

- Keep original spelling, accentuation and capitalisation (`j'ay`, `cy joint`,
  `isle`). Do not modernise.
- Preserve the original line breaks.
- **Never silently invent a reading.** Mark a doubtful word `[cette isle?]` and
  an unreadable one `[illisible]`. With cursive this is the failure mode that
  matters: a fluent guess is worse than a marked gap, because it cannot be
  distinguished from a real reading later.

## Gotchas

- **Only if you used `--transcriptions`:** on a Tropy without
  [#984](https://github.com/tropy/tropy/pull/984), `POST /transcriptions`
  writes to the database without updating application state, so neither the UI
  nor the API sees the new transcription until the project reloads. The data is
  there — verify with the DB rather than a read-back.
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
