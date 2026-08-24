# tropy-split-scans

A [Claude Code](https://docs.claude.com/en/docs/claude-code) **skill** that turns one batch-scanned archival item in your Tropy project into a clean set of document-level items — each with its own metadata, its own photos, and (for handwritten material) a transcription.

It's built for a specific but common archive-research workflow: you sit in a reading room and photograph a whole dossier, and it lands in Tropy as a single item holding a hundred-odd photos that are actually a dozen different letters, memoranda and *mémoires*. This skill helps Claude pull that pile apart into properly catalogued items, using **visual** document recognition rather than trusting OCR or an existing transcription.

Everything runs through **Tropy's local API** against the open project. The project database is never touched directly, so every change lands in Tropy's undo history and stays in sync with the UI.

---

## What it does

```
locate  ─►  inspect (Claude reads the page images)  ─►  write manifest  ─►  execute
```

1. **Locate** — Given an item id (or whatever is selected in Tropy), it fetches the item's photos and downloads each one as a rendered JPEG — rotation, mirroring and adjustments applied, i.e. what Tropy *displays* rather than the raw file on disk — in two renditions: a downscaled `scan/` copy and the full-size `full/` one. It also captures the dossier's own metadata.
2. **Inspect, in two passes** — Claude reads the *downscaled* images of every photo to find document boundaries, then the *full-resolution* first and last page of each document to read its metadata.
3. **Write the manifest** — Claude writes a `manifest.json` grouping photo ids into documents, with per-document metadata and, optionally, transcriptions.
4. **Execute** — The script **moves** the photos into document-level items, writes the metadata, attaches any transcriptions, tags everything `for review`, and verifies the result.

### Why two passes

Most photos in a dossier only have to answer one question — *does a new document start here?* — and that question survives downscaling, because its cues are visual: a change of hand, ink or paper, a salutation, a signature block, a blank verso, an address panel. Reading those at full resolution is wasted effort.

So pass 1 looks at every photo small and decides boundaries only. Pass 2 goes back at full resolution to just the first and last page of each document, where the title, correspondent and date live. On a 189-photo dossier holding ~40 documents, that's ~80 close reads instead of 189.

It also keeps segmentation independent of transcription, so transcription can be left to a dedicated tool (Transkribus, say) without changing how documents get found. A manifest with no `transcriptions` key produces items and metadata only.

## How the split actually works

Tropy has no "split this item into these groups" operation, but it has two primitives that compose into exactly that — both already undoable, both used by the UI:

- **Explode** moves each listed photo onto a *duplicate* of its item.
- **Merge** folds several items' photos, tags and lists back into one.

So the workflow explodes every assigned photo out of the dossier item — producing one single-photo item per photo, each a copy of the dossier — and then merges each document's photos back together. Photos are reassigned, never duplicated.

This has a pleasant side effect: because Explode duplicates the source item, **every new document item inherits the dossier's metadata for free** — identifier, archive, relation, source, rights, template, tags and lists all come across without being copied by hand. The manifest only supplies what is specific to the document.

These three routes (`explode`, `merge`, and a read-only `nav` that exposes the current UI selection) are **not in stock Tropy** — they're added by the companion `api-explode-merge` branch.

## What happens to the batch item

It survives, as an **empty dossier shell**: all its photos move out, but it keeps the dossier-level metadata, tags and lists. That shell is the record of the folder as a physical archival unit, and it means the workflow never deletes anything.

If some photos are left unassigned in the manifest, they stay on the shell and the script warns rather than failing — blank versos and separator shots often belong nowhere.

## How it handles metadata

Tropy stores metadata as RDF properties, so the script writes property URIs directly:

| Manifest field | Property | Type |
|---|---|---|
| `title` | `dc:title` | string |
| `creator` | `dc:creator` | string |
| `date` | `dc:date` | `tropy:date` — so `1777-1778` parses as a range |
| `type` | `dc:type` | string |
| `description` | `dc:description` | string |

Two deliberate conventions:

- **Titles are descriptive and document-specific** — `"Bourgeat à la Société royale de médecine"`, not the dossier's author-name title repeated on every document. The correspondent goes in `creator`.
- **Inherited fields never appear in the manifest.** Anything the dossier already carries comes across automatically; putting it in the manifest would just be a chance to get it wrong.

## How it handles handwriting

Archival OCR is shaky on 18th-century cursive, so the skill routes around it: Claude reads the *image* and produces the transcription from what it sees. The result goes into **Tropy's native transcription store** — the same place Tropy's own transcription feature writes — rather than into a note.

The editorial convention is **diplomatic, with uncertainty marked**:

- Original spelling, accentuation and capitalisation preserved (`j'ay`, `cy joint`, `isle`); nothing modernised.
- Original line breaks preserved.
- Doubtful readings marked `[cette isle?]`, unreadable ones `[illisible]`.

That last rule is the important one. A fluent guess is worse than a marked gap, because later on it can't be told apart from a real reading.

## Assumptions

- **One Tropy item per dossier, many documents inside.** The source is a batch item holding the photos of a whole archive folder.
- **The API is enabled and the project is open.** Port 2019 by default (2029 on beta/dev channels).
- **Visual inspection happens.** The whole point is that Claude *looks at the pages*.
- **The conventions are yours to change** — the `for review` tag, the empty-shell rule, the title convention and the transcription style are defaults, not requirements.

## Known wrinkles

These are Tropy-side, not skill-side:

- **Transcriptions don't appear until the project is reopened.** `POST /transcriptions` writes to the database but doesn't update application state. The data is there; the UI just hasn't heard about it.
- **Merged-away items read stale.** After a merge, `GET /items/:id` on a merged-away item still reports its old photos and `deleted:false`, though the database has it correctly trashed. Trust the merge response instead.

## Prerequisites

| Requirement | Notes |
|---|---|
| **Tropy with the local API enabled** | Preferences, or launch with `-p <port>`. The target project must be open. |
| **The `api-explode-merge` branch** | Adds `explode`, `merge` and `nav` to the API. Stock Tropy cannot move photos between items. |
| **Python 3.9+** | Standard library only. [Pillow](https://python-pillow.org/) is used for the pass-1 downscaling if it happens to be installed, `sips` on macOS otherwise; with neither, pass 1 falls back to full-size images. |
| **Claude Code** | The script is standalone and can be driven by hand, but the workflow assumes Claude is doing the visual inspection. |

## Setup

Claude Code auto-discovers skills in `~/.claude/skills/`, in a folder whose name matches the skill and containing `SKILL.md`:

```bash
git clone https://github.com/aaron-freedman/tropy-split-scans.git
mkdir -p ~/.claude/skills/tropy-split-scans
cp -R tropy-split-scans/SKILL.md tropy-split-scans/scripts ~/.claude/skills/tropy-split-scans/
```

Prefer a symlink if you want to keep pulling updates:

```bash
ln -s "$(pwd)/tropy-split-scans" ~/.claude/skills/tropy-split-scans
```

Then just ask, in natural language:

> "Split the dossier item 1069 into separate documents."
> "Break the selected Tropy item into its individual letters."

You can also run the script directly:

```bash
python3 scripts/tsplit.py locate 1069
python3 scripts/tsplit.py locate --selection --chunk 25 --overlap 3
python3 scripts/tsplit.py execute /tmp/tropy-split/1069/manifest.json --dry-run
python3 scripts/tsplit.py execute /tmp/tropy-split/1069/manifest.json
```

Useful flags: `--port` (default 2019), `--project` (a project id, or `current`), `--dry-run`, `--no-tag`.

## Repository layout

```
tropy-split-scans/
├── SKILL.md             # the skill definition Claude reads
├── scripts/
│   └── tsplit.py        # the locate/execute implementation
├── .gitignore
└── LICENSE              # MIT
```

## Prior version

This skill began as `zotero-split-scans`, which did the same job against a Zotero library and PDF batch scans. That version is preserved on the `main` branch.

## License

MIT — see [LICENSE](LICENSE).
