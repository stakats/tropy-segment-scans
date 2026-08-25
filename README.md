# tropy-segment-scans

A [Claude Code](https://docs.claude.com/en/docs/claude-code) **skill** that segments a batch-scanned archival item in your Tropy project into document-level items — each with its own photos and its own metadata.

It does one job: deciding where one document ends and the next begins, and making each one an item. It does not transcribe — Tropy already does that, via Transkribus.

It's built for a specific but common archive-research workflow: you sit in a reading room and photograph a whole dossier, and it lands in Tropy as a single item holding a hundred-odd photos that are actually a dozen different letters, memoranda and *mémoires*. This skill helps Claude pull that pile apart into properly catalogued items, using **visual** document recognition rather than trusting OCR or an existing transcription.

Everything runs through **Tropy's local API** against the open project. The project database is never touched directly, so every change lands in Tropy's undo history and stays in sync with the UI.

---

## Using it

Select the dossier item in Tropy and ask, in plain language:

> "Segment the selected item into separate documents."

That is the whole interaction. Claude fetches the photos, looks at them, proposes where the documents divide, and — once you agree — makes the items.

## What it does

```
locate  ─►  inspect (Claude reads the page images)  ─►  write manifest  ─►  execute
```

1. **Locate** — Given an item id (or whatever is selected in Tropy), it fetches the item's photos and downloads each one as a rendered JPEG — rotation, mirroring and adjustments applied, i.e. what Tropy *displays* rather than the raw file on disk — in two renditions: a downscaled `scan/` copy and the full-size `full/` one. It also captures the dossier's own metadata.
2. **Inspect, in two passes** — Claude reads the *downscaled* images of every photo to find document boundaries, then the *full-resolution* first and last page of each document to read its metadata.
3. **Write the manifest** — Claude writes a `manifest.json` grouping photo ids into documents, with each document's metadata.
4. **Execute** — The script **moves** the photos into document-level items, writes the metadata, tags everything `for review`, and verifies the result.

### Why two passes

Most photos in a dossier only have to answer one question — *does a new document start here?* — and that question survives downscaling, because it is answered by discontinuity rather than by reading: a change of hand, ink, paper or typeface, a heading or letterhead, a signature block, a blank page, text running off the bottom edge. Reading those at full resolution is wasted effort.

It also means the same cues work for printed and handwritten material alike, which is why the boundary policy is deliberately generic rather than tuned to one collection. It lives in its own file, [`segmentation.md`](segmentation.md), with its settings in [`segmentation.json`](segmentation.json), so it can be revised — or replaced for a particular collection — without touching the workflow or the script.

So pass 1 looks at every photo small and decides boundaries only. Pass 2 goes back at full resolution to just the first and last page of each document, where the title, correspondent and date live. On a 189-photo dossier holding ~40 documents, that's ~80 close reads instead of 189.

It also keeps segmentation independent of transcription, so the two can be done by the tool best suited to each.

## How the split actually works

Tropy has no "split this item into these groups" operation, but it has two primitives that compose into exactly that — both already undoable, both used by the UI:

- **Explode** moves each listed photo onto a *duplicate* of its item.
- **Merge** folds several items' photos, tags and lists back into one.

So the workflow explodes every assigned photo out of the dossier item — producing one single-photo item per photo, each a copy of the dossier — and then merges each document's photos back together. Photos are reassigned, never duplicated.

This has a pleasant side effect: because Explode duplicates the source item, **every new document item inherits the dossier's metadata for free** — identifier, archive, relation, source, rights, template, tags and lists all come across without being copied by hand. The manifest only supplies what is specific to the document.

These three routes (`explode`, `merge`, and a read-only `nav` that exposes the current UI selection) are **not in stock Tropy** — they're added by [tropy#985](https://github.com/tropy/tropy/pull/985).

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

## What it deliberately doesn't do

**It doesn't transcribe.** Tropy transcribes through Transkribus, which is built for handwriting and better at it than reading text off these images would be. Doing it here would mean a full-resolution pass over every page to produce a second-best result.

This matters for what you get at the end. Segmenting gives you correctly catalogued items, but a Tropy photo carries no text layer — so until they are transcribed, the new items have no searchable text. **Segmenting is half the job; run Tropy's transcription over the results to finish it.**

(The script can write transcriptions if a manifest carries them and you pass `--transcriptions`, but that is not what this tool is for.)

## Assumptions

- **One Tropy item per dossier, many documents inside.** The source is a batch item holding the photos of a whole archive folder.
- **The API is enabled and the project is open.** Port 2019 by default (2029 on beta/dev channels).
- **Visual inspection happens.** The whole point is that Claude *looks at the pages*.
- **The conventions are yours to change** — the `for review` tag, the empty-shell rule and the title convention are defaults, not requirements. The boundary policy is deliberately kept in its own file for exactly this reason.

## Known wrinkles

These are Tropy-side, not skill-side:

- **Merged-away items read stale.** After a merge, `GET /items/:id` on a merged-away item still reports its old photos and `deleted:false`, though the database has it correctly trashed. Trust the merge response instead.

## Prerequisites

| Requirement | Notes |
|---|---|
| **Tropy with the local API enabled** | Preferences, or launch with `-p <port>`. The target project must be open. |
| **[tropy#985](https://github.com/tropy/tropy/pull/985)** | Adds `explode`, `merge` and `nav` to the API. Released Tropy cannot move photos between items. |
| **Python 3.9+** | Standard library only. [Pillow](https://python-pillow.org/) is used for the pass-1 downscaling if it happens to be installed, `sips` on macOS otherwise; with neither, pass 1 falls back to full-size images. |
| **Claude Code** | The script is standalone and can be driven by hand, but the workflow assumes Claude is doing the visual inspection. |

## Setup

Claude Code auto-discovers skills in `~/.claude/skills/`, in a folder whose name matches the skill and containing `SKILL.md`:

```bash
git clone https://github.com/stakats/tropy-segment-scans.git
mkdir -p ~/.claude/skills/tropy-segment-scans
cp -R tropy-segment-scans/SKILL.md tropy-segment-scans/scripts ~/.claude/skills/tropy-segment-scans/
```

Prefer a symlink if you want to keep pulling updates:

```bash
ln -s "$(pwd)/tropy-segment-scans" ~/.claude/skills/tropy-segment-scans
```

Then select a dossier item in Tropy and ask:

> "Segment the selected item into separate documents."
> "Segment item 1069."

Claude runs the rest — fetching, looking, proposing boundaries, and making the items once you agree.

<details>
<summary>Running the script by hand</summary>

The inspection happens between fetching and writing, so by hand it is two commands with your own judgement in between:

```bash
python3 scripts/tsegment.py locate 1069          # or: locate --selection
# look at /tmp/tropy-segment/1069/scan/*.jpg, write manifest.json
python3 scripts/tsegment.py execute /tmp/tropy-segment/1069/manifest.json --dry-run
python3 scripts/tsegment.py execute /tmp/tropy-segment/1069/manifest.json
```

Flags: `--port` (default 2019), `--project` (a project id, or `current`), `--chunk` / `--overlap` / `--scan-edge` on `locate`, and `--dry-run`, `--no-tag`, `--transcriptions` on `execute`.

</details>

## Repository layout

```
tropy-segment-scans/
├── SKILL.md             # the workflow Claude follows
├── segmentation.md      # the boundary policy — revised on its own
├── segmentation.json    # its settings — revised on its own
├── NOTES.md             # observations awaiting promotion
├── PLUGIN-PORT.md       # findings for a future Tropy plugin
├── scripts/
│   └── tsegment.py      # the locate/execute implementation
├── .gitignore
└── LICENSE              # MIT
```

## Prior version

This skill began as [zotero-split-scans](https://github.com/stakats/zotero-split-scans), which did the same job against a Zotero library and PDF batch scans. That repository is kept as-is; this one carries its history forward.

## License

MIT — see [LICENSE](LICENSE).
