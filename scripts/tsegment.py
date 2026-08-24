#!/usr/bin/env python3
"""Split a batch-scanned Tropy item into document-level items.

Subcommands:
  locate  <item id | --selection>   Resolve the batch item and download each of
                                    its photos twice: a downscaled copy in
                                    scan/ for the boundary pass, and the full
                                    rendering in full/ for the metadata pass.
                                    Writes batch.json, a pass-1 window plan and
                                    a manifest template to the workdir.
  execute <workdir>/manifest.json   Move the photos into document-level items
                                    (explode + merge), write per-document
                                    metadata, attach transcriptions, verify.

Everything goes through Tropy's local API (Preferences > Advanced > enable the
API, or run Tropy with -p <port>). The project database is never touched
directly, so every change lands in Tropy's undo history.

The batch item is never deleted: once its photos have been moved out it remains
as an empty dossier shell carrying the dossier-level metadata, tags and lists.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

WORKROOT = Path("/tmp/tropy-segment")
DEFAULT_PORT = int(os.environ.get("TROPY_PORT", "2019"))
REVIEW_TAG = "for review"

# Longest edge of the downscaled copies used for the boundary pass. Big enough
# to see a change of hand, a signature block or a blank verso; small enough
# that a whole dossier can be looked at without reading every page closely.
SCAN_EDGE = 1024

# Tropy stores metadata as RDF properties. These are the ones the workflow
# writes per document; everything else is inherited from the batch item.
DC = "http://purl.org/dc/elements/1.1/"
TITLE = DC + "title"
CREATOR = DC + "creator"
DATE = DC + "date"
TYPE = DC + "type"
DESCRIPTION = DC + "description"

TROPY_DATE = "https://tropy.org/v1/tropy#date"
XSD_STRING = "http://www.w3.org/2001/XMLSchema#string"

# Fields a document may set in the manifest, mapped to their property URI.
# `date` is typed as a Tropy date so Tropy parses ranges like "1777-1778".
DOC_FIELDS = {
    "title": (TITLE, XSD_STRING),
    "creator": (CREATOR, XSD_STRING),
    "date": (DATE, TROPY_DATE),
    "type": (TYPE, XSD_STRING),
    "description": (DESCRIPTION, XSD_STRING),
}


class ApiError(Exception):
    pass


class Tropy:
    """Thin client for the Tropy local API."""

    def __init__(self, port=DEFAULT_PORT, project="current"):
        self.root = f"http://localhost:{port}"
        self.base = f"{self.root}/project/{project}"

    def _request(self, method, path, data=None, headers=None, raw=False):
        url = path if path.startswith("http") else self.base + path
        req = urllib.request.Request(url, data=data, method=method)
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = resp.read()
        except urllib.error.HTTPError as err:
            detail = err.read().decode("utf-8", "replace").strip()
            raise ApiError(f"{method} {url} -> {err.code} {detail}") from None
        except urllib.error.URLError as err:
            raise ApiError(
                f"cannot reach Tropy at {self.root} ({err.reason}). Is Tropy "
                f"running with the API enabled on this port?"
            ) from None
        if raw:
            return body
        if not body:
            return None
        return json.loads(body)

    def get(self, path, raw=False):
        return self._request("GET", path, raw=raw)

    def post_form(self, path, fields):
        """POST application/x-www-form-urlencoded, repeating keys for lists."""
        pairs = []
        for key, value in fields.items():
            if isinstance(value, (list, tuple)):
                pairs.extend((key, str(v)) for v in value)
            else:
                pairs.append((key, str(value)))
        body = urllib.parse.urlencode(pairs).encode()
        return self._request(
            "POST", path, data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"})

    def post_json(self, path, payload):
        body = json.dumps(payload).encode()
        return self._request(
            "POST", path, data=body,
            headers={"Content-Type": "application/json"})

    # -- endpoints ----------------------------------------------------

    def project(self):
        return self.get("/")

    def nav(self):
        return self.get("/nav")

    def item(self, item_id):
        return self.get(f"/items/{item_id}")

    def photos(self, item_id):
        return self.get(f"/items/{item_id}/photos")

    def metadata(self, subject_id):
        return self.get(f"/data/{subject_id}")

    def image(self, photo_id, fmt="jpg"):
        return self.get(f"/photos/{photo_id}/file.{fmt}", raw=True)

    def transcriptions(self, item_id):
        return self.get(f"/items/{item_id}/transcriptions")

    def tags(self):
        return self.get("/tags")

    def explode(self, item_id, photo_ids):
        return self.post_form(f"/items/{item_id}/explode", {"photo": photo_ids})

    def merge(self, item_ids):
        return self.post_form("/items/merge", {"item": item_ids})

    def save_metadata(self, subject_id, data):
        return self.post_json(f"/data/{subject_id}", data)

    def create_transcription(self, photo_id, text):
        return self.post_form(
            "/transcriptions", {"photo": photo_id, "text": text})

    def create_tag(self, name):
        return self.post_form("/tags", {"name": name})

    def add_tags(self, item_id, names):
        return self.post_form(f"/items/{item_id}/tags", {"tag": names})


# ---------------------------------------------------------------------
# locate
# ---------------------------------------------------------------------

def downscale(src, dest, max_edge):
    """Write a downscaled copy of `src` to `dest`.

    Tropy's extract endpoint renders at full size only, so the boundary-pass
    copies are made here. Pillow if it is installed, otherwise sips (macOS),
    otherwise give up and let the caller fall back to the full rendering.
    """
    try:
        from PIL import Image
    except ImportError:
        pass
    else:
        with Image.open(src) as img:
            img.draft("RGB", (max_edge, max_edge))  # cheap JPEG downscale
            img = img.convert("RGB")
            img.thumbnail((max_edge, max_edge), Image.LANCZOS)
            img.save(dest, "JPEG", quality=75)
        return True

    if shutil.which("sips"):
        result = subprocess.run(
            ["sips", "-Z", str(max_edge), str(src), "--out", str(dest)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if result.returncode == 0 and dest.exists():
            return True

    return False


def resolve_item(api, args):
    if args.selection:
        nav = api.nav()
        items = nav.get("items") or []
        if not items:
            sys.exit(
                "Nothing is selected in Tropy. Select the batch item in the "
                "project view, or pass an item id.")
        if len(items) > 1:
            sys.exit(
                f"{len(items)} items are selected ({items}). Select exactly "
                f"one batch item, or pass an item id.")
        return items[0]
    return args.item


def plan_chunks(count, size, overlap):
    """Windows of `size` photos overlapping by `overlap`, so a document that
    straddles a window boundary is still seen whole in the next window."""
    if count <= size:
        return [[1, count]]
    chunks = []
    start = 1
    while start <= count:
        end = min(start + size - 1, count)
        chunks.append([start, end])
        if end == count:
            break
        start = end - overlap + 1
    return chunks


def cmd_locate(args):
    api = Tropy(args.port, args.project)
    project = api.project()
    item_id = resolve_item(api, args)

    item = api.item(item_id)
    photos = api.photos(item_id)
    if not photos:
        sys.exit(f"Item {item_id} has no photos.")

    inherited = api.metadata(item_id)

    workdir = WORKROOT / str(item_id)
    full_dir = workdir / "full"
    scan_dir = workdir / "scan"
    for directory in (full_dir, scan_dir):
        directory.mkdir(parents=True, exist_ok=True)

    pages = []
    no_downscale = False
    for index, photo in enumerate(photos, start=1):
        # The extract endpoint renders the photo the way Tropy displays it
        # (rotation, mirroring and adjustments applied), which is what should
        # be inspected -- not the raw file on disk.
        full_path = full_dir / f"page-{index:03d}.jpg"
        scan_path = scan_dir / f"page-{index:03d}.jpg"
        error = None
        try:
            full_path.write_bytes(api.image(photo["id"]))
        except ApiError as err:
            error = str(err)
            print(f"WARNING: could not render photo {photo['id']}: {err}")

        scan = None
        if error is None:
            if downscale(full_path, scan_path, args.scan_edge):
                scan = str(scan_path)
            else:
                # No downscaler available: the boundary pass reads the full
                # rendering instead. Correct, just more to look at.
                no_downscale = True
                scan = str(full_path)

        pages.append({
            "page": index,
            "photo": photo["id"],
            "full": str(full_path) if error is None else None,
            "scan": scan,
            "filename": photo.get("filename"),
            "width": photo.get("width"),
            "height": photo.get("height"),
            "error": error,
        })

    if no_downscale:
        print("WARNING: no downscaler (install Pillow, or run on macOS for "
              "sips) -- the boundary pass will use full-size renderings.")

    existing = []
    try:
        found = api.transcriptions(item_id)
        if found:
            existing = found if isinstance(found, list) else [found]
    except ApiError:
        pass

    chunks = plan_chunks(len(pages), args.chunk, args.overlap)

    batch = {
        "project": project.get("project"),
        "project_id": project.get("id"),
        "port": args.port,
        "item": item_id,
        "lists": item.get("lists", []),
        "tags": item.get("tags", []),
        "template": item.get("template"),
        "inherited_metadata": inherited,
        "pages": pages,
        "chunks": chunks,
        "has_existing_transcriptions": bool(existing),
    }
    (workdir / "batch.json").write_text(json.dumps(batch, indent=2))

    template = {
        "item": item_id,
        "documents": [
            {
                "photos": [p["photo"] for p in pages[:1]],
                "title": "",
                "creator": "",
                "date": "",
                "type": "Correspondence",
                "transcriptions": {},
            }
        ],
    }
    (workdir / "manifest.template.json").write_text(
        json.dumps(template, indent=2))

    print(json.dumps({k: v for k, v in batch.items() if k != "pages"}, indent=2))
    print(f"\n{len(pages)} photos -> {workdir}")
    print(f"  pass 1 (boundaries): {scan_dir}/page-*.jpg")
    print(f"  pass 2 (metadata):   {full_dir}/page-*.jpg")
    if len(chunks) > 1:
        print(f"Pass 1 windows (page ranges, overlapping): {chunks}")
    print("Read the scan/ images to find document boundaries, then the full/ "
          "images of each document's first and last page for its metadata. "
          "Then write manifest.json (see manifest.template.json).")


# ---------------------------------------------------------------------
# execute
# ---------------------------------------------------------------------

def build_metadata(doc):
    data = {}
    for field, (prop, type_uri) in DOC_FIELDS.items():
        value = doc.get(field)
        if value:
            data[prop] = {"text": str(value), "type": type_uri}
    return data


def ensure_tag(api, name):
    """Item tags are added by name and resolved against existing tags, so the
    tag has to exist before it can be attached."""
    for tag in api.tags() or []:
        if tag.get("name") == name:
            return tag["id"]
    created = api.create_tag(name)
    if isinstance(created, dict):
        return created.get("id")
    return None


def cmd_execute(args):
    manifest_path = Path(args.manifest)
    workdir = manifest_path.parent
    manifest = json.loads(manifest_path.read_text())
    batch = json.loads((workdir / "batch.json").read_text())

    api = Tropy(args.port or batch.get("port", DEFAULT_PORT), args.project)

    item_id = manifest["item"]
    documents = manifest["documents"]
    if not documents:
        sys.exit("Manifest contains no documents.")

    live = api.item(item_id)
    available = list(live.get("photos") or [])

    assigned = [p for doc in documents for p in doc["photos"]]
    unknown = [p for p in assigned if p not in available]
    if unknown:
        sys.exit(
            f"Manifest references photos that are not on item {item_id}: "
            f"{unknown}")
    duplicates = sorted({p for p in assigned if assigned.count(p) > 1})
    if duplicates:
        sys.exit(f"Manifest assigns the same photo to more than one "
                 f"document: {duplicates}")

    missing = [p for p in available if p not in assigned]
    if missing:
        print(f"WARNING: photos left on the batch item (unassigned): {missing}")

    pending = sum(
        len(doc.get("transcriptions") or {}) for doc in documents)

    if args.dry_run:
        for index, doc in enumerate(documents, start=1):
            print(f"[{index}] photos={doc['photos']} "
                  f"title={doc.get('title')!r} date={doc.get('date')!r}")
        if args.transcriptions:
            print(f"\n{pending} transcription(s) will be written.")
        elif pending:
            print(f"\nSegmentation only: {pending} transcription(s) in the "
                  f"manifest will be ignored.")
        print(f"{len(documents)} documents, {len(assigned)} photos. "
              f"Nothing was changed.")
        return

    if pending and not args.transcriptions:
        print(f"Segmentation only: ignoring {pending} transcription(s) in the "
              f"manifest. Pass --transcriptions to write them.")

    # A single document covering every photo needs no restructuring: write the
    # metadata onto the batch item itself rather than shuffling photos around
    # into an identical new item.
    single = len(documents) == 1 and not missing

    if single:
        photo_to_item = {}
        print(f"Single document covering all photos -- updating item {item_id} "
              f"in place.")
    else:
        exploded = api.explode(item_id, assigned)
        photo_to_item = {}
        for entry in exploded["item"]:
            for photo in entry["photos"]:
                photo_to_item[photo] = entry["id"]
        print(f"Exploded {len(assigned)} photos out of item {item_id}.")

    tag_names = [REVIEW_TAG] if not args.no_tag else []
    if tag_names:
        ensure_tag(api, REVIEW_TAG)

    results = []
    for index, doc in enumerate(documents, start=1):
        photos = doc["photos"]

        if single:
            target = item_id
        else:
            item_ids = [photo_to_item[p] for p in photos]
            if len(item_ids) > 1:
                merged = api.merge(item_ids)
                target = merged["id"]
            else:
                target = item_ids[0]

        data = build_metadata(doc)
        if data:
            api.save_metadata(target, data)

        notes = 0
        transcriptions = (
            doc.get("transcriptions") or {}) if args.transcriptions else {}
        for photo_key, text in transcriptions.items():
            if not text:
                continue
            photo_id = int(photo_key)
            if photo_id not in photos:
                print(f"WARNING: document {index} has a transcription for "
                      f"photo {photo_id}, which is not one of its photos.")
                continue
            api.create_transcription(photo_id, text)
            notes += 1

        if tag_names:
            api.add_tags(target, tag_names)

        label = doc.get("title") or doc.get("creator") or f"document {index}"
        results.append({
            "item": target,
            "label": label,
            "photos": photos,
            "transcriptions": notes,
        })
        print(f"[{index}/{len(documents)}] item {target}  {label}  "
              f"photos {photos}  transcriptions={notes}")

    print("\n--- verification ---")
    for result in results:
        check = api.item(result["item"])
        actual = list(check.get("photos") or [])
        ok = actual == result["photos"]
        print(f"item {result['item']}: photos={actual} "
              f"{'ok' if ok else 'MISMATCH (expected ' + str(result['photos']) + ')'}")

    shell = api.item(item_id)
    if not single:
        remaining = list(shell.get("photos") or [])
        print(f"batch item {item_id}: photos={remaining} "
              f"{'(empty dossier shell)' if not remaining else ''}")

    (workdir / "results.json").write_text(json.dumps(results, indent=2))
    print(f"\n{len(results)} documents written. Results: "
          f"{workdir / 'results.json'}")
    if tag_names:
        print(f"Every new item is tagged {REVIEW_TAG!r}.")


# ---------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"Tropy API port (default {DEFAULT_PORT})")
    parser.add_argument("--project", default="current",
                        help="project id, or 'current' (default)")
    sub = parser.add_subparsers(dest="command", required=True)

    loc = sub.add_parser("locate", help="fetch a batch item for inspection")
    group = loc.add_mutually_exclusive_group(required=True)
    group.add_argument("item", nargs="?", type=int, help="batch item id")
    group.add_argument("--selection", action="store_true",
                       help="use the item selected in Tropy")
    loc.add_argument("--chunk", type=int, default=25,
                     help="photos per pass-1 window (default 25)")
    loc.add_argument("--overlap", type=int, default=3,
                     help="photos of overlap between pass-1 windows "
                          "(default 3)")
    loc.add_argument("--scan-edge", type=int, default=SCAN_EDGE,
                     dest="scan_edge",
                     help=f"longest edge of the pass-1 copies "
                          f"(default {SCAN_EDGE})")
    loc.set_defaults(func=cmd_locate)

    ex = sub.add_parser("execute", help="split the batch item per the manifest")
    ex.add_argument("manifest", help="path to manifest.json")
    ex.add_argument("--dry-run", action="store_true",
                    help="report what would be done, change nothing")
    ex.add_argument("--no-tag", action="store_true",
                    help=f"do not apply the {REVIEW_TAG!r} tag")
    ex.add_argument("--transcriptions", action="store_true",
                    help="also write any transcriptions the manifest carries; "
                         "off by default -- Tropy transcribes via Transkribus")
    ex.set_defaults(func=cmd_execute)

    args = parser.parse_args()
    try:
        args.func(args)
    except ApiError as err:
        sys.exit(f"API error: {err}")


if __name__ == "__main__":
    main()
