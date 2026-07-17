# Approach Document — CT-200 QA API

## 1. PDF Parsing Approach

### Why pdfplumber?
The CT-200 manual is a born-digital PDF (not scanned), so full OCR was unnecessary.
pdfplumber extracts text with layout awareness, preserving line breaks that are
critical for heading detection. PyMuPDF was considered but pdfplumber gave cleaner
line-by-line output for this specific document.

### Hierarchy Reconstruction
Headings are detected using a regex pattern that matches numbered section prefixes
(e.g. `1.`, `2.1`, `3.2.1`, `2.1.1.1`). The level is determined by counting the
dots in the section number. Parent-child relationships are built using a stack:
when a node of level N is encountered, all nodes of level >= N are popped from the
stack, and the remaining top of the stack becomes the parent.

### Structural Inconsistencies Found

| Issue | Description | How Handled |
|---|---|---|
| Out-of-order sections | Section 3.4 appears before 3.3 in both PDFs | Parser doesn't assume order — processes sequentially |
| Deep nesting without parent | 2.1.1.1 exists with no 2.1.1 | Stack-based parent resolution handles missing levels |
| Duplicate heading titles | "Error Codes" appears as 4.2 and 7.1 | Path (section number) used as unique identifier, not title |
| Section spanning pages | Section 8.1 splits across pages in V2 | pdfplumber processes page by page; body text is accumulated |

### What Initial Implementation Failed
The first version used `backref="parent"` with a self-referential SQLAlchemy
relationship without specifying `remote_side`, causing an ArgumentError. Fixed by
explicitly setting `primaryjoin` and `foreign_keys` on the relationship.

### How Failures Were Identified
- Manual inspection of the PDF before writing any code
- Running the parser and printing all extracted headings to verify structure
- Writing explicit unit tests targeting each known structural quirk
- Comparing node counts between V1 (32) and V2 (33) to verify new section detection

---

## 2. Data Model

### SQLite (Relational) — for structured versioned data
- **Document** — tracks name and version number
- **Node** — stores heading, level, body, path, content_hash, parent_id, version
- **Selection** — named, version-pinned bundle of nodes
- **SelectionItem** — links selection to specific node+version+hash

### JSON File Store — for LLM-generated output
MongoDB was the specified store but was replaced with a local JSON file
(`generations.json`) for simplicity. The assignment explicitly permits
"a well-justified JSON store." LLM outputs are append-only, schema-free,
and queried only by selection_id — making a document store appropriate.
In production, MongoDB or PostgreSQL JSONB would scale better.

---

## 3. Version Matching Strategy

### Approach: Path-based matching
Nodes are matched across versions using their section number path (e.g. `2.1.1.1`).
This is simple, fast, and works well for this document where section numbers are stable.

### Where it breaks
- If a section is renumbered (e.g. 3.2 becomes 3.3), the matcher treats it as a
  new node and orphans old test cases linked to the old path
- If two sections share the same number in different versions (edge case), a false
  match occurs
- Fuzzy title matching was considered but adds complexity and can produce false
  positives when similar headings exist (e.g. two "Error Codes" sections)

---

## 4. LLM Prompt Design

### Prompt Strategy
The prompt explicitly instructs the model to return ONLY a JSON object with no
markdown, no backticks, and no preamble. A concrete example of the expected format
is embedded in the prompt to reduce hallucination.

Input text is truncated to 2000 characters to avoid token limit errors on Groq's
free tier (400 errors were observed with longer inputs).

### Structured Output Validation
The response is:
1. Stripped of markdown fences (```json ... ```)
2. Parsed with `json.loads()`
3. Validated for the presence of the `test_cases` key
4. If any step fails, a structured error object is returned instead of raising

### Retry Strategy
No automatic retry is implemented. A failed generation returns:
```json
{
  "test_cases": [],
  "error": "reason",
  "status": "failed"
}
```
This is stored in generations.json so the failure is visible and queryable.
The user can resubmit via POST /generate. Auto-retry was skipped to avoid
burning free-tier API quota on repeated failures.

### Duplicate Submission Policy
- `/selections` — if the same name is submitted twice, the existing selection is
  returned. Rationale: selections are version-pinned snapshots; duplicating them
  adds no value.
- `/generate` — each call creates a new generation record. Rationale: the user
  may want to regenerate after a document update to get fresh test cases.

---

## 5. Staleness Detection

### Mechanism
At generation time, the content_hash of each selected node is stored alongside
the generated test cases. At retrieval time (GET /generations/{selection_id}),
the stored hash is compared against the current hash of the same node ID.

### Limitations
- **Binary detection only** — any change triggers a stale flag, whether it's a
  critical threshold change (300 → 250 cycles) or a typo fix. A one-word change
  gets the same flag as a safety-critical number change.
- **Node ID stability** — if a node is deleted and recreated (e.g. after full
  re-ingestion), the old node_id may not resolve, causing a false "not stale"
  result. This is a known gap.
- **No semantic diffing** — the system cannot tell whether a change is
  safety-significant. That would require LLM-based comparison of old vs new text,
  which is out of scope.

---

## 6. Decision Log

### Q: What's the one part most likely to silently give wrong results?
**Version matching by path.** If a section is renumbered between versions, the
matcher silently treats it as a new node and the old test cases are never flagged
as stale — they just quietly become unlinked. This would be caught by a
post-ingestion report showing unmatched nodes from the previous version.

### Q: Where did you choose simplicity over correctness?
**Path-based version matching.** It breaks the moment a section is renumbered.
In production, this would need fuzzy title matching or a manual review step for
unmatched nodes. The JSON file store is also a simplification — concurrent writes
would corrupt it.

### Q: Name one unhandled input
**A page that is entirely a scanned image embedded in the PDF.** pdfplumber would
return empty text for that page. The parser would silently skip it with no warning.
In production, this should trigger a logged warning and a partial-ingestion flag
on the document record.

---

## 7. What I Would Do Differently With More Time

- Add fuzzy title matching as a fallback for version matching
- Replace JSON store with MongoDB Atlas for concurrent-safe writes
- Add semantic staleness scoring (LLM compares old vs new text and rates impact)
- Add a post-ingestion diff report showing which nodes were added, changed, removed
- Add proper authentication and rate limiting
- Add a CI pipeline that runs pytest on every push
