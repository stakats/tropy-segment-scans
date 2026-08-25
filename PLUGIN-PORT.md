# Porting this to a Tropy plugin

Notes for a session that picks this up cold. Everything under "Verified" was
checked against the Tropy source at `1.18.0-beta.4`; everything under "To
verify" was not.

## The decision to make first

"Port it to a plugin" is not one thing, because **a plugin has no operator**.
Today the judgement — looking at sixty images and deciding where the documents
divide — is done by a model driving the tool. A plugin runs inside Tropy with
nobody driving it, so it has to call a model itself.

That gives three shapes, and they are not variations on each other:

1. **Full plugin.** Embeds the model calls. Installable by any Tropy user,
   needs no Claude Code. But it becomes an AI application to maintain: an API
   key in plugin options, per-run cost borne by the user, `segmentation.md`
   shipped as a prompt string, and a model deprecation treadmill.
2. **Plugin as mechanics only.** Provides a "Segment item…" action that
   consumes a manifest and performs the explode/merge/metadata work, with
   progress and a single undo entry. The judgement stays wherever a model is.
   The manifest format is already the interface between the two halves, so this
   is mostly a re-implementation of `scripts/tsegment.py` against the store.
3. **No plugin.** Land tropy#985 and keep the skill as it is.

Option 2 is the cheap one, because the split it needs already exists:
`segmentation.md` is judgement, `scripts/tsegment.py` is mechanics, and a
plugin would replace only the latter.

## Verified

**Hooks that Tropy actually invokes** — there is no "segment" hook, so a
segmentation plugin hangs off `export` (which appears in the item context menu):

| Hook | Invoked at |
|---|---|
| `import` | `src/commands/item/import.js:51` — `win.plugins.exec({id, action: 'import'})` |
| `export` | `src/commands/item/export.js:37` — `win.plugins.export(plugin, items)` |
| `extract` | `src/commands/photo/extract.js:53` |
| `transcribe` | `src/commands/photo/transcribe.js:94` |

Declared in the plugin's `package.json` under `hooks` (`src/common/plugins.js:229`).

**The plugin context** is `{ logger, dialog, json, sharp, window }` —
`src/window.js:44` passes `{dialog, json, sharp, window: this}`, and
`src/common/plugins.js:44` adds `logger`.

**A plugin can reach the Redux store.** `src/window.js:110` assigns
`this.store = store` on the `Window` instance, and the context carries
`window: this`. So `context.window.store.dispatch(...)` can dispatch
`item.explode`, `item.merge` and `metadata.save` directly, in process — no
HTTP, no API key, and no dependency on tropy#985.

**This is an escape hatch, not an API.** Reaching through `window.store` is
undocumented and nothing guarantees it. If option 2 is chosen, it is probably
worth proposing a real hook upstream rather than building on this.

## To verify

- The exact shape of what `win.plugins.export(plugin, items)` passes. It is
  expected to be JSON-LD, which would carry photo ids and paths — enough to
  identify photos — but confirm before designing around it.
- Whether an export-hook plugin can usefully *write* at all, or whether Tropy
  treats the hook as read-only by convention.
- Whether a plugin can add its own menu entry, or is confined to the
  import/export menus.

## Tropy internals worth carrying over

These took a while to establish and are what the current design rests on:

- **Explode + merge compose into a split.** `Explode` moves each listed photo
  onto a *duplicate* of its item; `Merge` folds items' photos, tags and lists
  back together. Both already register undo/redo. Explode every assigned photo
  out, then merge each document's photos back — photos are reassigned, never
  duplicated. See `src/commands/item/explode.js` and `merge.js`.
- **Metadata inheritance is free.** Because `Explode` duplicates the item via
  `mod.item.dup`, every new document arrives carrying the dossier's identifier,
  archive, relation, source, rights, template, tags and lists. Nothing copies
  them by hand.
- **The batch item survives as an empty shell.** Explode all its photos and it
  remains, holding the dossier-level record. Nothing is ever deleted.
- **Metadata is RDF.** `metadata.save` takes `{property URI: {text, type}}`;
  dates want `https://tropy.org/v1/tropy#date` so ranges like `1777-1778` parse.

## Traps that disappear in process

All artefacts of the HTTP hop, and none of them apply to a plugin: the `qs`
`arrayLimit` of 20 that silently mangles more than twenty repeated parameters
(tropy#985 fixes it), the API port confusion, and Tropy needing macOS
permission to read the photo folder.

One does *not* disappear: creating a transcription still does not update
application state before tropy#984, so it stays invisible until the project
reloads. Only relevant if transcription ever comes back into scope.

## Where things stand

- `tropy#985` — explode, merge, nav routes, plus the `arrayLimit` fix. Open.
- `tropy#984` — transcription state fix. Open, independent, verified to compose.
- This skill — used once in anger: 60 photos, 33 documents, ANOM E 157.
  `NOTES.md` records what that taught us.
- Open design question, deliberately parked: whether a `current` keyword for
  items and photos makes the `nav` endpoint redundant. Relevant to a plugin
  only if the plugin ends up talking HTTP after all.
