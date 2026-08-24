# Notes for refinement

Observations from real runs, kept here until they turn into changes.

## From ANOM E 157 (Dunois), 60 photos, 33 documents

**Wrappers come first, and there are usually two.** The dossier opened with a
modern descriptive label and then the archival cover ("N° 171 · Civil ·
Colonies E.157"). Both are covers, neither is a document. Worth saying
explicitly that the first one or two photos of a personnel dossier are
typically wrappers.

**These are microfilm surrogates, not direct photographs.** Boundary cue 3
("change in the photograph itself — background, lighting, camera distance")
was useless: every frame is identical because it is a film frame. The cue list
should carve this out — with a microfilm or flatbed surrogate, capture cues
carry no information and everything rests on paper, hand, ink and layout.

**Adjacent-leaf bleed is a false positive.** Many frames show a slice of the
neighbouring leaf at the edge, because the leaves were filmed stacked. That is
a capture artifact, not a second document and not a boundary.

**Drafts and their replies are separate documents, filed out of order.** The
dossier interleaves incoming letters with the ministry's own draft replies, and
the reply is sometimes filed *before* the letter it answers. Heavy
strikethrough and marginal insertion is the signature of a minute; that is a
document type worth recording rather than a defect.

**Dates do not run in order.** 1781 → 1793 → 1787 → an 11 → 1786. A date jump
supports a boundary, but date *sequence* proves nothing, and nothing should
assume monotonic order.

**Duplicates are normal and should each become an item.** Two copies of the
service record (pages 2 and 30), two versions of the same letter sent to
different recipients on the same day (pages 52 and 53). These are distinct
physical documents.

**Docket numbers are the most legible thing on the page.** N° 171, N° 199,
N° 897, N° 969, plus archival foliation, read clearly even downscaled, and are
excellent evidence of both boundary and identity. They deserve promotion in the
cue list.

**Marginal apostilles are part of the document.** "approuvé", "refusé", and
the marginal decisions on a rapport belong to the document they annotate.

**Two documents on one leaf really happens.** Page 43 carried both a bureau
exposé and the draft order that followed from it. The existing convention
handled it, so keep it.

**Documents can run past the edge of the dossier.** Page 38 breaks off
mid-sentence with no continuation present. Report it; never invent an ending.

## Efficiency

**Pass 2 should be exception-driven, not mechanical.** The design says pass 2
reads the first and last page of every document at full resolution. In practice
pass 1 at 1024px already yielded datelines, salutations, signatures, docket
numbers and titles for almost every document — 1024px is enough to *read* these
hands, not just to see their shape. Doing 33 documents × 2 pages of
full-resolution reading would mostly re-read what is already known.

Better: pass 1 records a confidence per document, and pass 2 visits only the
pages pass 1 flagged — an unreadable date, an uncertain correspondent, an
ambiguous boundary. On this dossier that would have been a handful of pages
rather than 66.

**Pass 1 is parallelisable and stateless.** "Does a document start on page N?"
depends almost entirely on pages N-1 and N. The windows in the plan are already
independent; they could run as concurrent subagents rather than serially in one
context, which is a wall-clock win that grows with dossier size.

**Pass 1 may not need a frontier model.** Discontinuity detection is a
perceptual judgement, and the three-question rule was written to be mechanical.
Worth measuring on a cheaper model before assuming. The risk is asymmetric: a
missed boundary yields one item holding two documents (easy to fix), while a
false boundary yields two half-documents carrying confident wrong metadata
(worse). Any cheaper model should be evaluated on false-boundary rate, not
overall accuracy.

This dossier is a usable benchmark: 60 photos, a known answer, and several
genuinely hard cases (the mid-sentence break, the two-drafts-on-one-leaf, the
duplicate pairs, the covers).

**Resolution is untested.** 1024px was chosen by argument, not measurement. If
the cues survive 768 or 512, pass 1 gets cheaper in proportion.

## Operational

Two failure modes cost more time than the segmentation itself, and both should
be in a troubleshooting section:

- Tropy lacking macOS permission to read the folder holding the photos. Every
  render returns 500 and the log shows `EPERM`. Now detected and reported.
- Two builds with the same product name. A locally built "Tropy Beta" and an
  installed "Tropy Beta" are indistinguishable in the Dock and in System
  Settings, so the permission can be granted to one and the app launched from
  the other. Giving a local build a distinct product name avoids this.
