---
name: tropy-split-scans
description: Split a batch-scanned Tropy item into document-level items. Use whenever you ask to "split" a Tropy dossier/batch item, break a folder of archive photos into separate documents (letters, memoranda, mémoires), or merge a batch of Tropy photos into discrete items. Works through Tropy's local API against the open project.
allowed-tools: Bash(python3:*) Read
---

# Tropy Split Scans

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
> prose here and the constants in `scripts/tsplit.py` to match your own.

## Prerequisites

- **Tropy's local API must be enabled** and the target project open.
  Default port 2019 (2029 on beta/dev channels); override with `--port`.
- **The `explode`, `merge` and `nav` routes must exist.** They are not in
  stock Tropy — they come from the `api-explode-merge` branch. Without them
  `execute` cannot move photos and will fail on the explode step.

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
python3 ~/.claude/skills/tropy-split-scans/scripts/tsplit.py locate <ITEM ID>
# or, acting on whatever is selected in Tropy:
python3 ~/.claude/skills/tropy-split-scans/scripts/tsplit.py locate --selection
```

Resolves the batch item, downloads every photo as a rendered JPEG (rotation,
mirroring and adjustments applied — what Tropy *displays*, not the raw file),
and writes to `/tmp/tropy-split/<itemId>/`:

- `page-001.jpg` … one per photo, in item order
- `batch.json` — photo ids, filenames, dimensions, the dossier's inherited
  metadata, and the **chunk plan**
- `manifest.template.json`

### 2. Inspect visually, chunk by chunk

**Read every page image** with the Read tool. `batch.json` gives a chunk plan —
overlapping windows of ~25 photos — because a 189-photo dossier will not fit in
one pass. The windows overlap by 3 photos so a document straddling a boundary is
still seen whole; when a document is still open at the end of a window, close it
in the next one rather than guessing.

Decide, for each document:

- **Boundaries** — which photos belong together.
- **Item metadata** — title, creator, date, type as visible on the document.
- **Whether it is handwritten** → transcribe from the image.

#### Document boundary cues

<!-- TODO: confirm with the researcher which of these actually hold for this
     collection, and how the dossiers are physically structured (bifolios,
     blank versos, address panels, folder covers, enclosures). -->

For 18th-century French manuscript correspondence, the reliable visual signals
are usually:

- **Opening and closing formulas** — a salutation (`Monsieur`, `Monseigneur`)
  starts a document; a subscription and signature (`votre très humble et très
  obéissant serviteur`) ends one.
- **A change of hand, ink or paper** — the single strongest cue, and one that
  only works visually.
- **The address panel or *dos*** — a folded bifolio often carries the address,
  and sometimes an archival note, on an otherwise blank outer face. That face
  belongs to the letter it wraps, and typically marks its end.
- **Blank or near-blank versos** — usually the tail of a document, not a
  document of their own.
- **Archival foliation and dossier covers** — numbering restarts, or a cover
  sheet names the correspondent, at the start of a new unit.

Enclosures (a *mémoire*, certificate or list travelling with a covering letter)
are a judgement call: keep them with the letter when the letter refers to them
and they carry no independent identity; make them their own item when they are
substantial and separately titled.

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
python3 ~/.claude/skills/tropy-split-scans/scripts/tsplit.py execute \
  /tmp/tropy-split/<itemId>/manifest.json --dry-run   # check first
python3 ~/.claude/skills/tropy-split-scans/scripts/tsplit.py execute \
  /tmp/tropy-split/<itemId>/manifest.json
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
everything is tagged `for review`. **Mention that transcriptions do not appear
until the project is reopened** (see below).

## Transcription

Handwriting is transcribed from the **image**, and lands in Tropy's native
transcription store (not a note), so it sits where Tropy's own transcription
feature puts it.

Editorial convention — **diplomatic, with uncertainty marked**:

- Keep original spelling, accentuation and capitalisation (`j'ay`, `cy joint`,
  `isle`). Do not modernise.
- Preserve the original line breaks.
- **Never silently invent a reading.** Mark a doubtful word `[cette isle?]` and
  an unreadable one `[illisible]`. With cursive this is the failure mode that
  matters: a fluent guess is worse than a marked gap, because it cannot be
  distinguished from a real reading later.

## Gotchas

- **Transcriptions are invisible until the project is reopened.** Tropy's
  `POST /transcriptions` writes to the database but does not update application
  state, so neither the UI nor the API shows them until the project reloads.
  The data is there — verify with the DB, not with a read-back.
- **Do not read back merged-away items.** After a merge, `GET /items/:id` on a
  merged-away item still reports its old photos and `deleted:false`, though the
  database has it correctly trashed. Trust the merge response.
- **The project must be open in Tropy.** The API resolves `current` to the
  focused project window; with nothing open every route returns
  `404 no project is open`.
- **`locate --selection` needs exactly one item selected** in the project view.
  Tropy tracks one current photo, not a multi-photo selection, so the selection
  addresses items.
- Large dossiers are slow to fetch — one rendered JPEG per photo. `locate` is
  read-only and safe to re-run.
