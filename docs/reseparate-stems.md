# Re-separate Stems Feature (src of record for regeneration)

> This is an **information-only reference**. It contains no literal code — only
> prose, exact signatures, field names, thresholds, and behaviors. Point an AI
> at this doc (as requirements) to regenerate the feature, which was deleted
> from the repo (local main restored to `origin/main` = `5e98fdd`, "v0.1.3").
>
> Reconstructed from the surviving SDD review diff packages, task reports, and
> the progress ledger (`docs/issues.md` is the separate design-decision history;
> this doc is the feature spec).

---

## 1. Overview

**Goal.** After the main isolation pass produces split stems (e.g. vocals,
drums, bass, `other`, `guitar`), the user may want to *re-run the separator on a
single existing stem* to break out an additional instrument without re-running
the whole track. On success the source stem is **replaced** in the mixer by its
new sub-stems.

**Scope.** Desktop (Streamlit `ui/`) only. No changes to the shared engine core
beyond two small pure helpers in `src/audio_to_tab/mixer.py`, and **no** changes
to `backend/`, `web/`, or the hosted stack.

**Replacement semantics.** A re-separate run on, say, the `other` stem produces
sub-stems (e.g. `guitar`). In the session, the `other` stem disappears and the
children appear *in its place* with composite ids (e.g. `other::guitar`). The
mixer board then shows the new children instead of the old source stem.

---

## 2. Feature 1 — Composite labels + RMS-energy helper (`src/audio_to_tab/mixer.py`)

### 2a. `stem_display_name` gains composite-id support
- **Signature:** `stem_display_name(stem_id: str) -> str`
- **New behavior:** if `stem_id` contains the composite separator `::`
  (`parent::child`), return a human label of the form **`Child (from Parent)`**.
  - Both `parent` and `child` parts are resolved independently: first through the
    existing stem-label map, then falling back to `replace("_", " ").title()`.
  - Example: `"other::guitar"` → `"Guitar (from Other)"`.
  - Example: `"other::synth"` (unknown child) → `"Synth (from Other)"`.
- **Plain ids unchanged:** `"guitar"` → `"Guitar"`, `"vocals"` → `"Vocals"`,
  `"lead_guitar"` → `"Lead Guitar"`, `"no_vocals"` → `"Instrumental"`.
- Composite handling is checked **before** the existing single-id label map, so
  composite ids are never misread as plain labels.

### 2b. New helper `stem_energy_db`
- **Signature:** `stem_energy_db(path: str | Path) -> float`
- **Behavior:** reads the wav and returns its RMS amplitude in **dBFS**
  (negative; ~0 dBFS = full scale).
  - Mono downmix if the file is multichannel (mean across channels).
  - Uses float64 precision internally to avoid overflow/underflow in the mean.
  - Near-silence floor: returns `-120.0` when RMS is below float32
    representable minimum.
- **Purpose.** Silence filter — it is what lets the feature discard a
  re-separate child that came out empty/silent (see 5a).
- **Test expectations:** a 440 Hz tone at amplitude 0.5 → ~`20*log10(0.5/sqrt(2))`
  ≈ −9 dBFS ±1 dB tolerance; an all-zero buffer → result `< −60`.

---

## 3. Feature 2 — Parent run-config persistence (`ui/common.py`)

### 3a. `write_run_metadata` gains an optional `config` param
- **Signature change (keyword-only):**
  `write_run_metadata(run_dir, *, page, title, artifacts, owner=None, source_kind=None, source_fingerprint=None, config=None)`
- **Behavior:** when `config` is a non-None dict, it is stored under a `"config"`
  key in the run's `meta.json` (serialized as-is). When `config` is None the key
  is **omitted** entirely (no existing callers change behavior).
- **Purpose.** Lets a re-separation default its separator model/quality to the
  **parent run's** settings even after an app restart, because the parent's
  config is persisted on disk.
- **Test expectations:** config dict round-trips exactly into `meta["config"]`;
  with config=None, `"config"` is absent from the meta dict.

---

## 4. Feature 3 — Re-separate job plumbing (`ui/isolate_jobs.py`)

### 4a. New `IsolateJobSpec` fields
- `reseparate_from: str | None = None`
- `parent_run_dir: str | None = None`
- Both are plain dataclass fields; round-trip through `to_dict()` / `from_dict()`
  is automatic (the `from_dict` field-name filter already ignores unknown keys and
  carries known ones).

### 4b. `_run_one_job` success path
- When `spec.reseparate_from` is set:
  - **Skip** `write_run_metadata`. Re-separate children must **not** become
    separate "Recent" runs — they belong to the parent run on disk.
  - Include the two new fields (`reseparate_from`, `parent_run_dir`) in the
    `write_status(...)` call (they travel along so the session can act on them).
- The normal (non-re-separate) success path is **unchanged** (still writes
  metadata). Error/abort paths untouched.

### 4c. New helper `_rewrite_parent_meta`
- **Signature:** `_rewrite_parent_meta(parent_run_dir: str | None, session)`.
- **Behavior:** reads `<parent_run_dir>/meta.json`, **replaces only its
  `artifacts` dict** with the session's current merged artifacts, and writes back
  **atomically** (write to a temp file, then `replace` the original).
  - Preserves every other key in the parent meta (e.g. `config`, `title`,
    `created_at`, `source_kind` / `source_fingerprint`).
  - Silent no-op if `parent_run_dir` is falsy, the `meta.json` is missing, or it
    fails to parse.

### 4d. Re-separate branch in `apply_succeeded_job_to_session`
- Inserted at the **top** of the function, right after the
  `status.get("status") != "succeeded"` guard, **before** the normal result path.
- When `status.get("reseparate_from")` is present:
  1. Import the state helpers `children_from_outputs` and `merge_reseparate`
     from `ui.isolate_state`.
  2. `children = children_from_outputs(run_dir)` (run_dir = this job's output dir).
  3. **If `children` is empty** (all children near-silent): return `False` and
     leave the session **unchanged** — the source stem must survive.
  4. Otherwise merge: `merged = merge_reseparate(artifacts, source_stem, children)`
     (source stem removed, children added with composite keys `source_stem::child`).
     Store `merged` into `session["isolate_artifacts"]`.
  5. Update `session["isolate_selected_stems"]`: remove the old `source_stem`
     entry; add `{f"{source_stem}::{child}": True}` for each child.
  6. Re-point the run directory back to the **parent**: set both
     `isolate_run_dir` and `isolate_viewing_run_dir` to `parent_run_dir`.
     (Children are written into the parent's output dir, not a new run.)
  7. **Do NOT** overwrite `isolate_results_source_fp` or `isolate_source_kind` —
     the parent's source fingerprint stays authoritative.
  8. Call `_rewrite_parent_meta(parent_run_dir, session)`.
  9. Pop all `_MIXER_RESET_KEYS` (reset the mixer workspace).
  10. Record `session["isolate_consumed_job_id"] = status.get("id")`; return `True`.
- The **normal** (non-re-separate) path that follows is byte-for-byte untouched.

---

## 5. Feature 3 — Merge helpers (`ui/isolate_state.py`)

### 5a. `children_from_outputs`
- **Signature:** `children_from_outputs(output_dir: Path) -> dict[str, Path]`
- **Behavior:** scans `output_dir` for `.wav` files and returns a mapping
  `{child_stem_id: Path}` where `child_stem_id` is the **raw** filename stem
  (e.g. `guitar` from `guitar.wav`).
  - Skips any file whose name contains a diagnostic marker (the marker string is
    `"diagnostic"`).
  - Drops children whose `stem_energy_db` is **≤ −40.0 dBFS** (near-silent).
  - Returns `{}` when the dir is missing or no audible children remain.
- **Why raw ids.** The parent stem id is **not** stored in the output dir, so the
  scan cannot know it. The caller builds the composite `parent::child` key (see
  4d). This is the correct division: `children_from_outputs` is a pure scanner
  with no knowledge of parent context.

### 5b. `merge_reseparate`
- **Signature:** `merge_reseparate(artifacts, source_stem, children) -> dict`
- **Behavior:** returns a **new** dict with `source_stem` removed and each child
  key/value (already composite-prefixed by the caller) added. Never mutates the
  input `artifacts` dict.

### 5c. `stem_label_for_id`
- **Signature:** `stem_label_for_id(stem_id: str) -> str`
- **Behavior:** thin wrapper over `stem_display_name` from `audio_to_tab.mixer`
  (so composite ids get the `Child (from Parent)` label everywhere).

### 5d. Test expectations (the 5 added)
- `children_from_outputs` filters near-silent children; empty dir → `{}`;
  diagnostic-named files skipped.
- `merge_reseparate` removes the source key and adds children without mutating
  the input.
- `stem_label_for_id` renders a composite id with the `Child (from Parent)` form.

---

## 6. UI plan (designed, **never implemented**)

The engine + job plumbing (sections 2–5) are what existed. The user-facing UI
was **planned but never built**:

- A "Break down a stem" expander/control placed in `_render_mixer_workspace`,
  positioned **after** the guitar fix-up panel.
- Per-stem control that enqueues an `IsolateJobSpec` pointed at that stem's wav,
  with separator model/quality **defaulting from the parent run's persisted
  config** (the value saved by Feature 2).
- "Fold other" behavior **off by default**.
- Rides the existing serial in-process job queue; no new concurrency machinery.

If recreating this feature, build sections 2–5 first, then this panel.

---

## 7. Design decisions / gotchas

- **Composite keys** (`source_stem::child`) are built by the **caller** in
  `apply_succeeded_job_to_session`, not by `children_from_outputs`.
- **Children stay out of "Recent".** Re-separate jobs skip `write_run_metadata`;
  only the parent run is listed.
- **Parent fingerprint is authoritative.** Re-separation never overwrites the
  parent's source fingerprint/kind.
- **Empty child result is safe.** No audible children → the source stem is left
  untouched (returns `False`).
- **Parent config survives.** `_rewrite_parent_meta` only touches `artifacts`, so
  the parent's persisted `config` is preserved for future defaulting.
- **Desktop-only feature.** Hosted stack and shared engine core carried only the
  two pure `mixer.py` helpers.
- **UI panel missing.** The engine/job plumbing existed; the on-screen control
  was designed but never implemented.

---

## 8. Recreating the feature

To regenerate:
1. Describe the "Replacement semantics" in section 1 and the "Design decisions"
   in section 7 first — they anchor the design.
2. Implement in this order: section 2 (mixer helpers + tests), section 3
   (config persistence + tests), section 5 (state merge helpers + tests),
   section 4 (job plumbing), then section 6 (UI panel).
3. Desktop-only; run against `ui/` with the existing test suite.

---

## 9. Note on excluded work (YouTube output-name WIP)

A separate, *unrelated* piece of local work (output-name / YouTube title
handling) had been bundled into the intermediate commit that was code-reviewed
for this feature. It was **split out** and excluded from the actual re-separate
feature commit, and is out of scope of this doc. If that work is later wanted,
it must be redone independently — it is not described here.
