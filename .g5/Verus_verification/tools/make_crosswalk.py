#!/usr/bin/env python3
"""Reconcile both arms' register sources into the three registers and write the mechanical crosswalk.

    python3 .g5/Verus_verification/tools/make_crosswalk.py

Reads (never writes) the imported playbook trees and the guidance arm's registers at 24c6b0c0, and writes:

- `.g5/Verus_verification/{bugs_issues,design_simplification,open_questions}.md`: every guidance-arm entry is kept as
  written (anchor, text, order within its severity). A playbook source that has the same trigger and effect as a
  guidance entry (MERGES below, each confirmed by reading both entries) becomes an "Also recorded as" line in that
  entry. Every other playbook source becomes a compact entry under its own ID, placed by severity; withdrawn,
  refuted, not-reproduced and duplicate records, unfiled candidates and inherited proof debt go to sections after
  the actionable entries. Generated text ends with GEN_MARK and is regenerated on every run; hand-written entries
  (no mark) are kept.
- `.g5/Verus_verification/crosswalk/{findings,simplifications,questions}.tsv`: one row per source ID.
- `.g5/Verus_verification/crosswalk/evidence-errata.tsv`: the playbook arm's errata (corrections to registered run
  records, not register entries), one row each.

Standard library only. Run from the repository root.
"""
from __future__ import annotations

import csv
import glob
import json
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
V = REPO / ".g5/Verus_verification"
PC = REPO / "experiment/playbook-completion"
PU = REPO / "experiment/playbook-uplift"
G_TIP = "24c6b0c03e1c84cac6691de45c183fa1cf73940b"
REL_PC = "../../experiment/playbook-completion"
REL_PU = "../../experiment/playbook-uplift"
GEN_MARK = "_Imported from the playbook arm by `tools/make_crosswalk.py`; regenerate rather than edit._"
RECONCILIATIONS = {
    "F-1804": "Iteration 6 strengthening, not a new discovery: actual fresh temporal writer -> snapshot -> one-call/paged window preserves weights but changes integer attrs n=1 to string n='1'. The initial DISAGREES receipt170720 and intended type-preservation oracle remain. temporal_restore now models Number -> NumericText scalar export separately from weight coercion and attribute type, with a distinguishing Verus theorem. A method-copy proposal merely removing str(value) failed on actual Decimal JSON serialization and is retired as insufficient; no repair implemented. Owner install.snapshot.temporal.",
    "F-C1802": "Iteration 6 strengthening: a real Native API <SUBSCRIPT> refusal for one temporal KG line is caught, while valid neighboring events restore, failed_rows stays empty and KG is reported restored. temporal_restore::theorem_swallowed_line_is_not_reported derives that outcome; native layout/zero/valid neighbors retained. The intended error-reporting obligation is still violated. This corroborates the inherited root, not a new defect. Owner install.snapshot.temporal.",
    "F-1802": "Iteration 5 strengthening: the generic first-column merge guard is the same root as bug-plt-004; both IDs/history are retained, not counted as two new findings. Real IRIS merge with preexisting graph B's shared node skips graph A's parent and refuses A's routed vector by FK, while B's existing vector is counted restored but unchanged. snapshot_routes now derives restore_parent -> load -> read and distinguishes an existing incompatible row's successful skip from an empty incompatible table's refusal. Original complete-archive prediction/DISAGREES receipt retained; no repair implemented.",
    "F-C0351": "Iteration 4 strengthening, not a new discovery: independent review of edge_acceptance found the caller marker input missing from its first transcription. The extended run/theorem_caller_marker_retained and 56 actual Python/SQLite cases now include temporal=True on insertion and repeated adoption: True/True, one row, final caller value and marker retained. The prior live verify omission remains inherited, not rerun. temporal.structural.adopt preserves ADR-0009's intended unmarked explicit edge and names this observed exception. No reserve/strip repair is implemented; the SQL/provider boundary remains conditional.",
    "RC-16": "Iteration 3 corroboration: aql_frontend now checks integer-range lexing, typed depth propagation, literal null operators and text-null distinction through the public execute_aql handoff. It does not establish traversal results, Cypher-to-SQL semantics or a general reference evaluator. Preserve exact lower/upper bounds, string versus null and parameter handoff in any proposed shared frontend; the general simplification remains unimplemented.",
    "F-1004": "Iteration 3 comparison: the create-an-edgeless-start-node trigger/effect is also bug-plt-017; the two source records are retained, not counted as separate new discoveries. The refuted deletion premise here is not restored. New pagerank_admission is global PageRank only and explicitly does not cover PPR; its node-key success cannot repair or refute this PPR finding.",
    "F-1003": "Iteration 3 scope reconciliation: algorithms.cache.pagerank separates COUNT:MAX cache admission from the numerical/every-node promise. PageRankGlobalJson:506-520 still caps output at 10000; the new native Python binding only forwards normalized fixture scores and does not rerun this live cap witness. No normalization or unlimited-output proof is claimed; HD-1004 remains authoritative as previously recorded.",
    "F-0709": "Iteration 2 corroboration: fusion_ranking now models raw list first-rank selection and the Python wrapper's asymmetric provider catches. Its unit binding runs actual multi_modal_search, retaining empty successful legs but omitting failed vector/graph legs while raising text errors. The providers are substituted; no new IRIS observation or new discovery is claimed. bug-srch-010 concerns the engine surface, while this wrapper evidence belongs to F-0709. Owner: search.fusion.failed_leg and search.fusion.python; no shared repair implemented.",
    "HD-0702": "Iteration 2 reconciliation: the G canonical question provisionally favors a common zero absent contribution; the P intent file instead defaults to documenting distinct surfaces. Both are unratified proposals, not conflicting product observations. Preserve both options; the new Python-only RRF proof settles neither a product-wide rule nor which text corpus is intended. Owner: search.fusion.absent.",
    "HD-0705": "Iteration 2 owner recovery: search.fusion.python.support makes this policy visible from the canonical ontology. Preserve the intent file's correction: only RRFFusion and TextSearchEngine are exported at top level; HybridSearchFusion is module-level. The new contract covers shipped RRFFusion/HybridSearchFusion behavior without declaring all three supported public API.",
    "RC-28": "Iteration 2 corroboration: reconstruction now derives zero/default meta normalization and per-record count checks, with an actual named-reader/export unit comparison. The model distinguishes transient oversize from final size; this supports one resource-bound boundary only. Streaming memory remains q-con-001 and peak/final policy is q-iter-002. No common capacity mechanism was implemented or proved. Iteration 3 addition: vector_threshold checks inclusive cosine predicates before limits and binds the repeated vector/threshold. PageRank's hidden 10000-row Owner cap remains F-1003. Neither a threshold proof nor a successful cache hit establishes all-node numerical normalization; no general capacity mechanism was implemented.",
    "F-0813": "Iteration 1 scope reconciliation: the original title 'Values carry no stored type' is too broad at 3eaa79cf. Its live witness concerns relationship qualifier filters and remains valid. Nodes written as numbers retain D/N types, numeric-looking node strings stay strings, and 4.7.0 node filters distinguish them (KNOWN_ISSUES.md:183-240; prop_values.py:110-126,211-231). The new node_read contract/binding corroborates that narrower boundary; it does not withdraw the relationship finding or establish all sorting/arithmetic semantics. Owner: query.conformance and query.values.",
    "RC-17": "Iteration 1 scope reconciliation: retain the seven inherited member findings and the proposed shared encoding, but do not read this burden as absence of all node typing. The Python numeric writer, CY_TYPED D/N/S protocol and batched reader already share one typed numeric path (models/node_read/NOTES.md). Preserve integer versus float, numeric-looking text, escaped marks, booleans and legacy text if simplifying it. Relationship qualifier filters remain the decisive F-0813 contrast. No shared-storage repair was implemented or proved here.",
    "F-0406": "Iteration 1 comparison: warm_sources models WarmAll's source census and stamp admission, not independent cache deletion. The inherited clear-cache/current-stamp witness remains a product gap; the new proof must not be read as repairing it. The canonical warm owner now states globals-only enumeration and this exception.",
}

def reconciled(text):
    """Preserve explicit scope corrections when regenerating imported entries."""
    for fid,note in RECONCILIATIONS.items():
        pattern = r'(<a id="' + re.escape(fid) + r'"></a>\n.*?)(?=\n<a id=|\Z)'
        def add(m):
            entry=m.group(1)
            if note in entry: return entry
            return entry.replace(GEN_MARK,note + "\n\n" + GEN_MARK)
        text=re.sub(pattern,add,text,flags=re.S)
    return text
ALSO_MARK = "(crosswalk)"
SEVS = ["Critical", "High", "Medium", "Low", "Unranked"]
MAP_SEV = {"S1": "High", "S2": "Medium", "S3": "Low", "S4": "Low"}
LOWER = {"Critical": "High", "High": "Medium", "Medium": "Low", "Low": "Low", "Unranked": "Unranked"}
COLS = ["source_arm", "source_id", "source_path", "canonical_id", "relation", "trigger key", "effect key",
        "source disposition", "source severity", "mapped severity", "evidence strength", "owning block"]

# Same trigger and effect, confirmed by reading both entries (reviewed plan section 7.2).
MERGES = {
    "F-1303": "bug-001", "F-C1201": "bug-002", "F-C1301": "bug-002", "F-1304": "bug-003",
    "F-C1203": "bug-led-007", "F-C1308": "bug-led-007", "F-C0702": "bug-srch-002", "F-0501": "bug-tmp-002",
    "F-0402": "bug-str-002", "HD-1301": "simp-001", "HD-1801": "q-plt-004",
}
# Related but not the same question (kept separate, cross-referenced).
RELATED = {"HD-1201": ["q-004"], "HD-1305": ["q-010"], "F-1306": ["q-010"], "F-1801": ["q-plt-004"]}
RENUMBERED = {"F-C1103": "F-C1107", "F-C1104": "F-C1108", "F-C1105": "F-C1109"}
SPLIT = {"F-1102a": "F-1102", "F-1102b": "F-1102", "F-1103b": "F-1103"}
UNFILED = ["F-C0811", "F-C1711", "F-C0111", "F-C0511", "F-C0512", "F-C0513", "F-C1011"]
MODULE_OWNER = {"00": "root, access.", "01": "install.", "02": "graph. / structure.", "03": "structure. / install.bulk_load",
                "04": "structure.", "05": "temporal.", "06": "search.", "07": "search.", "08": "query.", "09": "query.",
                "10": "algorithms.", "11": "ledger.", "12": "erasure.", "13": "redaction.", "14": "ledger.readers",
                "15": "fhir.", "16": "access.", "17": "install. / access. / adapters.", "18": "install.snapshot"}


def git(*a):
    return subprocess.run(["git", "-C", str(REPO), *a], capture_output=True, text=True).stdout


def one_line(s, n=400):
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def md_safe(s):
    # keep imported text inert inside an entry: no headings, anchors or status-line look-alikes
    s = one_line(s, 600).replace("<a id=", "&lt;a id=")
    return re.sub(r"^(#+|Severity:|Run:|Found by:|Reproduced by:|Comparison:|Sources?:)", r"\\\1", s)


# ---------------------------------------------------------------- registers

def split_register(text):
    """(preamble, [entries], trailing) where entries are the actionable entries before the first `## ` heading."""
    first = text.find('<a id="')
    pre = text[:first]
    rest = text[first:]
    m = re.search(r"^## ", rest, re.M)
    body, trailing = (rest[: m.start()], rest[m.start():]) if m else (rest, "")
    entries = [e for e in re.split(r'(?=^<a id=")', body, flags=re.M) if e.strip()]
    return pre, entries, trailing


def entry_id(e):
    return re.match(r'<a id="([^"]+)"></a>', e).group(1)


def entry_sev(e):
    m = re.search(r"^Severity:\s*(\w+)", e, re.M)
    return m.group(1) if m else "Unranked"


def strip_generated(text):
    pre, entries, trailing = split_register(text)
    entries = [e for e in entries if GEN_MARK not in e]
    entries = [re.sub(r"\n\nAlso recorded as: [^\n]*" + re.escape(ALSO_MARK) + r"[^\n]*", "", e) for e in entries]
    # trailing: drop generated sections (each starts with a `## ` heading carrying the arm label)
    parts = re.split(r"(?=^## )", trailing, flags=re.M)
    trailing = "".join(p for p in parts if "(playbook arm)" not in p.split("\n", 1)[0] and GEN_MARK not in p.split("\n", 1)[0])
    return pre, entries, trailing


def add_also(entry, line):
    lines = entry.rstrip("\n").split("\n")
    # after the status line and an optional Run: line
    idx = next(i for i, l in enumerate(lines) if l.startswith("Severity:"))
    j = idx + 1
    while j < len(lines) and not lines[j].strip():
        j += 1
    if j < len(lines) and lines[j].startswith("Run:"):
        idx = j
    lines[idx + 1:idx + 1] = ["", f"Also recorded as: {line} {ALSO_MARK}"]
    return "\n".join(lines) + "\n\n"


# ---------------------------------------------------------------- playbook sources

def audit_findings():
    recs = {}
    order = sorted(glob.glob(str(PC / "findings/audit/*.json")))

    def walk(x, f):
        if isinstance(x, dict):
            i = x.get("id")
            if isinstance(i, str) and re.match(r"^F-[A-Z0-9]+$", i) and "title" in x:
                recs.setdefault(i, []).append((f, x))
            for v in x.values():
                walk(v, f)
        elif isinstance(x, list):
            for v in x:
                walk(v, f)
    for f in order:
        walk(json.load(open(f)), f)
    # the later file wins (reflection/ROOT-CAUSES.md)
    return {i: (Path(v[-1][0]).name, v[-1][1], [Path(a).name for a, _ in v]) for i, v in recs.items()}


def uplift_finding_ids():
    ids = set()
    for f in [PU / "FINDINGS.md", *sorted((PU / "findings").glob("*.md"))]:
        ids |= set(re.findall(r"^#+ (F-[0-9A-Z]+)", f.read_text(), re.M))
    return ids


def hd_decisions():
    out = {}
    for f in [PU / "DECISIONS.md", *sorted((PU / "decisions").glob("*.md"))]:
        t = f.read_text()
        for m in re.finditer(r"^### (HD-[0-9]+) (.*?)\n(.*?)(?=^### |\Z)", t, re.M | re.S):
            out[m.group(1)] = {"title": m.group(2).strip(), "body": m.group(3), "path": f}
    for i, d in out.items():
        intent = PC / "intent" / f"{i}.md"
        d["intent"] = intent if intent.exists() else None
        st = ""
        if intent.exists():
            sm = re.search(r"^Status:\s*\*\*(\w+)\*\*([^\n]*)", intent.read_text(), re.M)
            st = (sm.group(1) + one_line(sm.group(2), 300)) if sm else ""
        d["status"] = st
        dm = re.search(r"Default applied until decided:\s*(.*?)(?:\n- |\Z)", d["body"], re.S)
        d["default"] = one_line(dm.group(1), 300) if dm else ""
        qm = re.search(r"Question:\s*(.*?)(?:\n- |\Z)", d["body"], re.S)
        d["question"] = one_line(qm.group(1), 500) if qm else one_line(d["title"])
    return out


def root_causes():
    t = (PC / "reflection/ROOT-CAUSES.md").read_text()
    out = {}
    for m in re.finditer(r"^### (RC-[0-9]+) (.*?)\n(.*?)(?=^### |\Z)", t, re.M | re.S):
        body = m.group(3)
        g = lambda k: one_line((re.search(rf"^- {k}:\s*(.*?)(?=\n- |\Z)", body, re.M | re.S) or [None, ""])[1], 500)
        fids = re.findall(r"^\s+- (F-[0-9A-Z]+) \[(S\d)", body, re.M)
        hs = re.search(r"Highest severity (S\d)", body)
        cnt = re.search(r"Findings \((\d+)\)", body)
        out[m.group(1)] = {"title": m.group(2).strip(), "statement": g("Statement"), "violates": g("Violates"),
                           "remedy": g("Remedy \\(prose only\\)") or g("Remedy"), "findings": fids,
                           "highest": hs.group(1) if hs else "", "count": int(cnt.group(1)) if cnt else len(fids)}
    return out


def proof_debt():
    out = {}
    for line in (PC / "PROOF-DEBT.md").read_text().splitlines():
        m = re.match(r"^\| (D-\d+) \| (.*)", line)
        if m:
            cells = [c.strip() for c in m.group(2).split(" | ")]
            out[m.group(1)] = cells
    return out


def reach_items():
    t = (PC / "ontology/12-erasure.md").read_text() + (PC / "ontology/13-redaction.md").read_text()
    out = {}
    for line in t.splitlines():
        for r in re.findall(r"REACH-([1-5])", line):
            sid = re.match(r"^\| ([A-Z]{3}-[A-Za-z0-9.]+) \|", line)
            text = re.match(r"^\|[^|]*\|[^|]*\|[^|]*\| ([^|]*)\|", line)
            out.setdefault(f"REACH-{r}", []).append((sid.group(1) if sid else "?", text.group(1).strip() if text else ""))
    return out


def control_receipts():
    """finding id (F-0206 / FC-1001 / HD-1003) -> (crate family, control receipt, baseline receipt) from this run."""
    out = {}
    for fam_dir in sorted(glob.glob(str(V / "results/playbook-*"))):
        base, ctl = None, {}
        for f in sorted(glob.glob(f"{fam_dir}/*/receipt.json")):
            d = json.load(open(f))
            if d.get("kind") != "playbook-crate-rerun":
                continue
            rel = str(Path(f).relative_to(V))
            if d["label"] == "baseline" and d["verdict"] == "PASS":
                base = rel
            elif d["verdict"] == "EXPECTED_FAIL":
                ctl[d["label"]] = rel
        for label, rel in ctl.items():
            m = re.match(r"control_(f|fc|hd)(\d{4})_", label)
            if m and base:
                fid = {"f": "F-", "fc": "F-C", "hd": "HD-"}[m.group(1)] + m.group(2)
                out.setdefault(fid, []).append((Path(fam_dir).name, label, rel, base))
    return out


def owner_blocks():
    """register entry id -> ontology blocks whose metadata links it."""
    out = {}
    for page in (REPO / ".g5/ontology").rglob("*.g5.md"):
        t = page.read_text()
        meta = t.split("\n## Metadata", 1)[-1]
        for m in re.finditer(r"^### (\S+)\n(.*?)(?=^### |\Z)", meta, re.M | re.S):
            for e in re.findall(r"(?:bugs_issues|design_simplification|open_questions)\.md#([A-Za-z0-9._-]+)", m.group(2)):
                out.setdefault(e, []).append(m.group(1))
    return out


# ---------------------------------------------------------------- entries

def finding_entry(fid, rec, also_ids, ctl, title_prefix=""):
    f, x, files = rec
    src = x.get("severity", "")
    disp = x.get("disposition", "")
    mapped = MAP_SEV.get(src, "Unranked")
    native = disp == "reproduced-live"
    sev = mapped if native else LOWER[mapped]
    ev = x.get("evidence") or []
    refs = [f"{e.get('kind')} `{e.get('ref')}`" for e in ev if isinstance(e, dict)]
    live = [e.get("ref") for e in ev if isinstance(e, dict) and e.get("kind") in ("live", "probe")]
    obs = x.get("observed") or {}
    verdict = obs.get("verdict") if isinstance(obs, dict) else obs
    mod = str(x.get("module", ""))
    title = "Relationship filters conflate numeric-looking strings and numbers" if fid == "F-0813" else x.get("title")
    lines = [f'<a id="{fid}"></a>', f"### {title_prefix}{one_line(title, 200)}", "",
             f"Severity: {sev} · Decision: Open", "", "Run: Playbook uplift and completion audit, 2026-11-13/14 (imported 2026-11-14)", ""]
    if not native:
        lines += [f"**Suspected** here: the playbook arm's disposition is `{disp}`, not a native reproduction; severity is one level below the mapped {mapped}.", ""]
    if disp == "intent-undecided":
        lines += ["**Policy-dependent:** the playbook arm classed the expected behavior as undecided intent.", ""]
    if disp == "blocked-access":
        lines += ["**Conditional:** the playbook arm could not reach the deciding state (`blocked-access`).", ""]
    lines += [f"Found by: playbook arm, [{f}]({REL_PC}/findings/audit/{f}) ({'; '.join(refs[:6]) or 'no evidence list'})", "",
              f"Reproduced by: {('playbook arm, live on its IRIS (x86_64 VM): ' + ', '.join(f'`{r}`' for r in live[:4])) if native and live else ('playbook arm, live on its IRIS (x86_64 VM)' if native else 'none (' + disp + ')')}", "",
              f"- Expected: {md_safe(x.get('intended'))}",
              f"- Observed at the pin: {md_safe(verdict or x.get('notes'))}",
              f"- Source severity {src}, confidence {x.get('confidence', '')}; module {mod}; governing page here: `{MODULE_OWNER.get(mod[:2], mod)}`.",
              f"- Remedy proposed by the playbook arm (not implemented): {md_safe(x.get('remedy'))}"]
    if ctl.get(fid):
        c = ctl[fid][0]
        lines.append(f"- Reviewed-design control: `{c[0]}` `{c[1]}` fails where expected in this run ([receipt]({c[2]})); the reviewed design verifies ([baseline]({c[3]})). That is a model fact about the reviewed design, not a product property.")
    if also_ids:
        lines.append(f"- Related: {', '.join(also_ids)}.")
    if len(files) > 1:
        lines.append(f"- Recorded in {', '.join(files)}; the later file's record is used.")
    lines.append("- Not yet compared with the guidance arm's entries beyond the confirmed merges.")
    lines += ["", GEN_MARK, "", ""]
    return "\n".join(lines), sev, mapped


def withdrawn_entry(fid, rec):
    f, x, files = rec
    disp = x.get("disposition", "")
    lines = [f'<a id="{fid}"></a>', f"### {one_line(x.get('title'), 200)}", "", "Severity: Unranked", "",
             f"- Playbook arm disposition: `{disp}` ([{f}]({REL_PC}/findings/audit/{f})); source severity {x.get('severity', '')}.",
             f"- Reason recorded: {md_safe(x.get('notes') or (x.get('observed') or {}).get('verdict') if isinstance(x.get('observed'), dict) else x.get('notes'))}"]
    if x.get("duplicate_of"):
        lines.append(f"- Duplicate of {x['duplicate_of']}.")
    lines += ["", GEN_MARK, "", ""]
    return "\n".join(lines)


def main():
    (V / "crosswalk").mkdir(exist_ok=True)
    audit = audit_findings()
    up_ids = uplift_finding_ids()
    hds = hd_decisions()
    rcs = root_causes()
    debt = proof_debt()
    reach = reach_items()
    ctl = control_receipts()
    owners = owner_blocks()
    g_anchor = {n: set(re.findall(r'<a id="([^"]+)"></a>', git("show", f"{G_TIP}:.g5/Verus_verification/{n}")))
                for n in ("bugs_issues.md", "design_simplification.md", "open_questions.md")}

    rows = {"findings.tsv": [], "simplifications.tsv": [], "questions.tsv": []}

    # ---------------- bugs_issues.md
    name = "bugs_issues.md"
    pre, entries, trailing = strip_generated((V / name).read_text())
    by_id = {entry_id(e): i for i, e in enumerate(entries)}
    also = {}
    for pid, gid in MERGES.items():
        if pid.startswith("F-") and gid in by_id:
            also.setdefault(gid, []).append(pid)
    for gid, pids in also.items():
        bits = []
        for p in pids:
            f, x, _ = audit[p]
            bits.append(f"{p} (playbook arm, {x.get('severity')}, {x.get('disposition')}; [{f}]({REL_PC}/findings/audit/{f}))")
        g_sev = entry_sev(entries[by_id[gid]])
        p_sev = {MAP_SEV.get(audit[p][1].get('severity'), 'Unranked') for p in pids}
        note = "" if p_sev == {g_sev} else f" Severity differs: here {g_sev}, playbook {'/'.join(sorted(audit[p][1].get('severity') for p in pids))}; both are kept."
        entries[by_id[gid]] = add_also(entries[by_id[gid]], "; ".join(bits) + "." + note)
    new_act, withdrawn = [], []
    for fid in sorted(audit):
        if fid in MERGES:
            continue
        f, x, files = audit[fid]
        disp = x.get("disposition", "")
        if disp in ("refuted", "not-reproduced", "duplicate", "withdrawn"):
            withdrawn.append(withdrawn_entry(fid, audit[fid]))
            continue
        text, sev, mapped = finding_entry(fid, audit[fid], RELATED.get(fid, []), ctl)
        new_act.append((sev, fid, text))
    acts = [(entry_sev(e), i, e) for i, e in enumerate(entries)] + [(s, 10 ** 6 + n, t) for n, (s, _, t) in enumerate(new_act)]
    acts.sort(key=lambda a: (SEVS.index(a[0]), a[1]))
    cand = ["## Candidates not filed (playbook arm)", "",
            "Candidate findings named by the playbook arm's stopped lock-plan lane (`lockplans/PARTIAL.md`, `STATUS.md`); not findings, kept so no ID is lost. Their drafts are not cited.", ""]
    for c in UNFILED:
        where = "STATUS.md and PROOF-DEBT.md (lock-plan lane)" if c in ("F-C0811", "F-C1711") else f"a lock-plan draft (`lockplans/{c[4:6]}.json`, PENDING-LIVE)"
        cand += [f'<a id="{c}"></a>', f"### Unfiled candidate {c}", "", "Severity: Unranked", "",
                 f"- Named in {where}; not filed as a finding by the playbook arm, not reproduced or examined here.", "", GEN_MARK, "", ""]
    wd = ["## Withdrawn, refuted and not reproduced (playbook arm)", "",
          "Playbook-arm finding records whose own disposition withdraws them. They stay here with the recorded reason.", "", *withdrawn]
    out = pre + "".join(e for _, _, e in acts) + trailing.rstrip("\n") + "\n\n" + "\n".join(wd).rstrip("\n") + "\n\n" + "\n".join(cand).rstrip("\n") + "\n"
    (V / name).write_text(reconciled(out))
    anchors_now = set(re.findall(r'<a id="([^"]+)"></a>', out))
    for gid in sorted(anchors_now):
        if gid in audit or gid in UNFILED:
            continue
        arm = "G" if gid in g_anchor[name] else "C"
        e = re.search(r'<a id="' + re.escape(gid) + r'"></a>\n(.*?)(?=\n<a id=|\Z)', out, re.S).group(1)
        title = one_line(e.split("\n", 1)[0].lstrip("# "), 120)
        trig = (re.search(r"`([A-Za-z0-9_/.\-]+\.(?:py|cls|md|sql)[:#][^`]*)`", e) or [None, ""])[1]
        rep = re.search(r"^Reproduced by:\s*(.*)$", e, re.M)
        local_native = re.search(r"iteration\s+(\d+)\s+real IRIS", rep.group(1), re.I) if rep else None
        strength = (f"native (local iteration {local_native.group(1)}; scoped reproduction, see entry)" if local_native else
                    "native (guidance VM)" if rep and not rep.group(1).lower().startswith("none") else
                    "model witness" if "receipt.json" in e else "source")
        if "Severity:" in e and "Decision:" not in e.split("\n")[2:5].__str__():
            strength = "observation"
        rows["findings.tsv"].append([arm, gid, f".g5/Verus_verification/{name}" if arm == "G" else f".g5/Verus_verification/{name} (consolidated)",
                                     gid, "same", trig, title, "Open" if "Decision: Open" in e else "observation",
                                     entry_sev(e), entry_sev(e), strength, ";".join(owners.get(gid, []))])
    for fid in sorted(audit):
        f, x, files = audit[fid]
        disp = x.get("disposition", "")
        canon = MERGES.get(fid, fid)
        rel = "merged-into" if fid in MERGES else {"refuted": "refuted", "not-reproduced": "not-reproduced",
                                                  "duplicate": "duplicate", "withdrawn": "withdrawn"}.get(disp, "same")
        insp = next((e.get("ref") for e in (x.get("evidence") or []) if isinstance(e, dict) and e.get("kind") == "inspected"), "")
        mapped = MAP_SEV.get(x.get("severity"), "Unranked")
        mod = str(x.get("module", ""))
        rows["findings.tsv"].append(["P", fid, f"experiment/playbook-completion/findings/audit/{f}" + (" (also in the uplift's findings/NN.md)" if fid in up_ids else ""),
                                     canon, rel, insp, one_line(x.get("title"), 120), disp, x.get("severity", ""),
                                     entry_sev(re.search(r'<a id="' + re.escape(canon) + r'"></a>\n(.*?)(?=\n<a id=|\Z)', out, re.S).group(1)),
                                     disp, ";".join(owners.get(canon, [])) or MODULE_OWNER.get(mod[:2], mod)])
    for old, new in RENUMBERED.items():
        rows["findings.tsv"].append(["P", old, "experiment/playbook-completion/correspondence/RENUMBERED.md", new, "superseded",
                                     "", f"renumbered at merge to {new}", "renumbered", "", "", "", ""])
    for old, new in SPLIT.items():
        rows["findings.tsv"].append(["P", old, "experiment/playbook-completion/evidence/runs (run label)", new, "split", "",
                                     f"a sub-case label of {new} in registered runs", "sub-case", "", "", "", ""])
    for c in UNFILED:
        rows["findings.tsv"].append(["P", c, "experiment/playbook-completion/lockplans/PARTIAL.md" if c in ("F-C0811", "F-C1711") else f"experiment/playbook-completion/lockplans/{c[4:6]}.json",
                                     c, "candidate-unfiled", "", "unfiled lock-plan candidate", "candidate", "", "Unranked", "none", ""])
    for u in sorted(up_ids - set(audit)):
        rows["findings.tsv"].append(["P", u, "experiment/playbook-uplift/findings", u, "not-reproduced", "", "uplift finding with no audit record", "", "", "", "", ""])

    # ---------------- design_simplification.md
    name = "design_simplification.md"
    pre, entries, trailing = strip_generated((V / name).read_text())
    by_id = {entry_id(e): i for i, e in enumerate(entries)}
    if "simp-001" in by_id:
        entries[by_id["simp-001"]] = add_also(entries[by_id["simp-001"]],
            f"HD-1301 (playbook decision: should the redaction's opening check and its marker be one locked step; [DECISIONS.md]({REL_PU}/DECISIONS.md), intent [HD-1301]({REL_PC}/intent/HD-1301.md)).")
    new_act = []
    for rid, rc in rcs.items():
        sev = MAP_SEV.get(rc["highest"], "Low")
        # a reviewed design with a control that reintroduces the pin's behavior, among the root cause's findings
        checked = []
        for fid, _s in rc["findings"]:
            for c in ctl.get(fid, []):
                checked.append(c)
        comp = (f"[{checked[0][0]} `{checked[0][1]}` (as built)]({checked[0][2]}) → [reviewed design]({checked[0][3]}) — "
                f"a reviewed model that removes this burden for one member finding ({len(checked)} such controls rerun here); the rest is prose only") if checked else \
            "none — the playbook arm's remedy is prose only; no model compares it here"
        lines = [f'<a id="{rid}"></a>', f"### {rc['title']}", "", f"Severity: {sev} · Decision: Open", "",
                 "Run: Playbook completion audit, reflection lane r3 (imported 2026-11-14)", "",
                 f"Comparison: {comp}", "",
                 f"- Burden today: {md_safe(rc['statement'])}",
                 f"- Findings that share it: {rc['count']} (highest {rc['highest']}): {', '.join(f for f, _ in rc['findings'][:30])}{'…' if len(rc['findings']) > 30 else ''}.",
                 f"- Rule it breaks: {md_safe(rc['violates'])}",
                 f"- Redundant decision a shared mechanism would remove, and the proposal (not implemented): {md_safe(rc['remedy'])}",
                 f"- Caller behavior to preserve and a distinguishing case: not stated by the playbook arm beyond the remedy; see each member finding's `Expected` line.",
                 f"- Source: [reflection/ROOT-CAUSES.md]({REL_PC}/reflection/ROOT-CAUSES.md). Not yet compared with the guidance arm's simplifications.",
                 "", GEN_MARK, "", ""]
        new_act.append((sev, rid, "\n".join(lines)))
    acts = [(entry_sev(e), i, e) for i, e in enumerate(entries)] + [(s, 10 ** 6 + n, t) for n, (s, _, t) in enumerate(new_act)]
    acts.sort(key=lambda a: (SEVS.index(a[0]), a[1]))
    out = pre + "".join(e for _, _, e in acts) + trailing.rstrip("\n") + "\n"
    (V / name).write_text(reconciled(out))
    for gid in sorted(set(re.findall(r'<a id="([^"]+)"></a>', out))):
        if gid in rcs:
            continue
        arm = "G" if gid in g_anchor[name] else "C"
        e = re.search(r'<a id="' + re.escape(gid) + r'"></a>\n(.*?)(?=\n<a id=|\Z)', out, re.S).group(1)
        rows["simplifications.tsv"].append([arm, gid, f".g5/Verus_verification/{name}", gid, "same", "", one_line(e.split("\n", 1)[0].lstrip("# "), 120),
                                            "Open" if "Decision: Open" in e else "observation", entry_sev(e), entry_sev(e),
                                            "model comparison" if "receipt.json" in e else "proposal", ";".join(owners.get(gid, []))])
    for rid, rc in rcs.items():
        rows["simplifications.tsv"].append(["P", rid, "experiment/playbook-completion/reflection/ROOT-CAUSES.md", rid, "same", "",
                                            rc["title"], "root cause", rc["highest"], MAP_SEV.get(rc["highest"], "Low"),
                                            f"{rc['count']} findings", ""])
    rows["simplifications.tsv"].append(["P", "HD-1301", "experiment/playbook-uplift/DECISIONS.md; experiment/playbook-completion/intent/HD-1301.md",
                                        "simp-001", "merged-into", "", hds.get("HD-1301", {}).get("title", ""), hds.get("HD-1301", {}).get("status", ""),
                                        "", "High", "reviewed proof (playbook-uplift/proofs)", ";".join(owners.get("simp-001", []))])

    # ---------------- open_questions.md
    name = "open_questions.md"
    pre, entries, trailing = strip_generated((V / name).read_text())
    by_id = {entry_id(e): i for i, e in enumerate(entries)}
    if "q-plt-004" in by_id:
        entries[by_id["q-plt-004"]] = add_also(entries[by_id["q-plt-004"]],
            f"HD-1801 (playbook decision: what should a restore do to the live ledger; [decisions/18.md]({REL_PU}/decisions/18.md), intent [HD-1801]({REL_PC}/intent/HD-1801.md)); the matching finding is F-1801 in the bugs register.")
    new_act = []
    for hid in sorted(hds):
        if hid in MERGES:
            continue
        d = hds[hid]
        st = d["status"].lower()
        klass = ("settled by authority, as the playbook arm recorded it (not re-checked here)" if st.startswith("supported")
                 else "needs ratification (the playbook arm's working assumption)")
        rel = RELATED.get(hid, [])
        lines = [f'<a id="{hid}"></a>', f"### {one_line(d['title'], 200)}", "", "Severity: Unranked · Decision: Open", "",
                 "Run: Playbook uplift, decisions for the human (imported 2026-11-14)", "",
                 f"- Question: {md_safe(d['question'])}",
                 f"- Classification: {klass}.",
                 f"- Working answer: {md_safe(d['default']) or 'see the intent file'}.",
                 f"- Intent recovery: {('[intent/' + hid + '.md](' + REL_PC + '/intent/' + hid + '.md)') if d['intent'] else 'none'} (status {md_safe(d['status'])[:300] or 'none'}); decision text [{d['path'].name}]({REL_PU}/{d['path'].relative_to(PU)}).",
                 f"- Owner: the maintainer (a human decision; no human has decided it).",
                 f"- Related here: {', '.join(rel)} (related, not the same question)." if rel else "- Not yet compared with the guidance arm's questions.",
                 "", GEN_MARK, "", ""]
        new_act.append(("Unranked", hid, "\n".join(lines)))
    for rid in sorted(reach):
        stmts = reach[rid]
        lines = [f'<a id="{rid}"></a>', f"### Should erasure and redaction reach the store in {rid}?", "", "Severity: Unranked · Decision: Open", "",
                 "Run: Playbook completion audit, residual maintainer questions (imported 2026-11-14)", "",
                 f"- Today: {md_safe(' / '.join(f'{s}: {t}' for s, t in stmts[:2]))}",
                 f"- Classification: needs ratification; the playbook arm's working answer is to name every store a removal does not reach ([STATUS.md]({REL_PC}/STATUS.md)).",
                 f"- Owner: the maintainer. Related: HD-1304, HD-1101, HD-1401.",
                 "", GEN_MARK, "", ""]
        new_act.append(("Unranked", rid, "\n".join(lines)))
    acts = [(entry_sev(e), i, e) for i, e in enumerate(entries)] + [(s, 10 ** 6 + n, t) for n, (s, _, t) in enumerate(new_act)]
    acts.sort(key=lambda a: (SEVS.index(a[0]), a[1]))
    debt_lines = ["## Inherited verification debt (playbook arm)", "",
                  f"Proof debt the playbook arm recorded in [PROOF-DEBT.md]({REL_PC}/PROOF-DEBT.md). These are verification gaps, not product questions; they stay visible here.", ""]
    for did, cells in debt.items():
        debt_lines += [f'<a id="{did}"></a>', f"### Proof debt {did}: {md_safe(cells[0])[:180]}", "", "Severity: Unranked", "",
                       f"- {md_safe(' | '.join(cells[1:]))[:900]}", "", GEN_MARK, "", ""]
    out = pre + "".join(e for _, _, e in acts) + trailing.rstrip("\n") + ("\n\n" if trailing.strip() else "\n") + "\n".join(debt_lines).rstrip("\n") + "\n"
    (V / name).write_text(reconciled(out))
    for gid in sorted(set(re.findall(r'<a id="([^"]+)"></a>', out))):
        if gid in hds or gid in reach or gid in debt:
            continue
        arm = "G" if gid in g_anchor[name] else "C"
        e = re.search(r'<a id="' + re.escape(gid) + r'"></a>\n(.*?)(?=\n<a id=|\Z)', out, re.S).group(1)
        rows["questions.tsv"].append([arm, gid, f".g5/Verus_verification/{name}", gid, "same", "", one_line(e.split("\n", 1)[0].lstrip("# "), 120),
                                      "Open" if "Decision: Open" in e else "observation", entry_sev(e), entry_sev(e), "", ";".join(owners.get(gid, []))])
    for hid, d in sorted(hds.items()):
        if hid == "HD-1301":
            continue  # crosswalked to simp-001 in simplifications.tsv
        rows["questions.tsv"].append(["P", hid, f"experiment/playbook-uplift/{d['path'].relative_to(PU)}; intent/{hid}.md", MERGES.get(hid, hid),
                                      "merged-into" if hid in MERGES else "same", "", one_line(d["title"], 120), one_line(d["status"], 80),
                                      "", "Unranked", "intent recovery", ";".join(owners.get(MERGES.get(hid, hid), []))])
    for rid in sorted(reach):
        rows["questions.tsv"].append(["P", rid, "experiment/playbook-completion/STATUS.md; ontology/12-erasure.md; ontology/13-redaction.md", rid, "same", "",
                                      f"reach of erasure and redaction ({rid})", "residual question", "", "Unranked", "", "erasure.;redaction."])
    for did in debt:
        rows["questions.tsv"].append(["P", did, "experiment/playbook-completion/PROOF-DEBT.md", did, "same", "", f"proof debt {did}",
                                      "verification debt", "", "Unranked", "", ""])

    for tsv, rs in rows.items():
        with open(V / "crosswalk" / tsv, "w", newline="") as f:
            w = csv.writer(f, delimiter="\t", lineterminator="\n")
            w.writerow(COLS)
            w.writerows(rs)
    # errata
    er = []
    for path in (PC / "evidence/errata.json", PC / "reflection/errata-proposed.json"):
        d = json.load(open(path))
        for x in d.get("errata", []):
            txt = json.dumps(x)
            fids = sorted(set(re.findall(r"\bF-C?[0-9]{4}\b", txt)))
            er.append([x.get("id"), str(path.relative_to(REPO)), one_line(x.get("correction") or x.get("note") or "", 200),
                       ";".join(fids), "evidence correction to a registered run record; carried, not a register entry"])
    with open(V / "crosswalk/evidence-errata.tsv", "w", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(["erratum_id", "source_path", "correction", "finding IDs named", "disposition"])
        w.writerows(er)
    print({k: len(v) for k, v in rows.items()}, "errata", len(er))


if __name__ == "__main__":
    main()
