#!/usr/bin/env python3
"""Project existing iris evidence into the G5 viewer contract; preserve the source registers."""

import csv
import json
import os
import re
from collections import defaultdict
from pathlib import Path

VERIFICATION_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = VERIFICATION_DIR.parents[1]


def relative(p):
    return p.relative_to(REPO_ROOT).as_posix()


def link(base, path, title):
    return f"[{title}]({os.path.relpath(path, base)})"


def table(name):
    with (VERIFICATION_DIR / name).open() as f:
        return list(csv.DictReader(f, delimiter="\t"))


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def build():
    registered = {
        r["family_id"]: r for r in table("families.tsv") if r["kind"] == "verus"
    }
    families = {
        r["path"].split("/")[-1]
        if r["path"].startswith(".g5/Verus_verification/models/")
        else fid: r
        for fid, r in registered.items()
    }
    for model in sorted((VERIFICATION_DIR / "models").glob("*/model.json")):
        families.setdefault(
            model.parent.name,
            {
                "family_id": model.parent.name,
                "path": relative(model.parent),
                "scope": model.parent.name.replace("_", " "),
                "status": "later uplift evidence",
                "design": "as-built",
            },
        )
    owners = defaultdict(set)
    statements = {}
    for page in (VERIFICATION_DIR.parent / "ontology").rglob("*.g5.md"):
        for block in re.split(
            r"(?m)^### ", page.read_text().partition("\n## Metadata")[2]
        )[1:]:
            sid, _, metadata = block.partition("\n")
            statements[sid] = metadata
            for name, desc in families.items():
                if (
                    re.search(
                        r"/models/"
                        + re.escape(name)
                        + r"/(?!manifest\.json|BINDINGS\.md)[^)\s]+",
                        metadata,
                    )
                    or f"`{desc['family_id']}`" in metadata
                ):
                    owners[name].add(sid)
    names = {r["family_id"]: name for name, r in families.items()}
    for row in table("crosswalk/decision-links.tsv"):
        if row["block"] in statements and row["family"] in names:
            owners[names[row["family"]]].add(row["block"])
    rows = []
    for name, desc in sorted(families.items()):
        folder = VERIFICATION_DIR / "models" / name
        folder.mkdir(exist_ok=True)
        source = REPO_ROOT / desc["path"]
        definition = source / "model.json"
        config = json.loads(definition.read_text()) if definition.exists() else {}
        native = {}
        notes = source / "NOTES.md"
        if notes.exists():
            for p in (VERIFICATION_DIR / "receipts/native").glob("*.json"):
                if p.stem in notes.read_text() or p.stem.startswith(name + "_"):
                    native[p] = p.stem
        checks = {}
        records = sorted((VERIFICATION_DIR / "results" / name).glob("*/receipt.json"))
        for p in [*records, *sorted(native)]:
            x = json.loads(p.read_text())
            if not isinstance(x, dict):
                continue
            obs = x.get("observed")
            obs = obs if isinstance(obs, dict) else {}
            kind = "native" if p in native else x.get("kind", "observed")
            control = x.get("control") or {}
            label = (
                native.get(p)
                or x.get("label")
                or (control.get("name") if isinstance(control, dict) else control)
                or kind
            )
            label = str(label)
            run_id = p.stem if p in native else p.parent.name
            outcome = str(x.get("verdict") or "unadjudicated")
            if (
                obs.get("timed_out")
                or obs.get("has_resource_limit")
                or outcome in ("ERROR", "HARNESS_ERROR")
            ):
                assessment = "incomplete"
            elif outcome in ("AGREES", "PASS", "EXPECTED_FAIL"):
                assessment = "matched"
            elif outcome in ("UNEXPECTED", "FAIL_ELSEWHERE", "SURVIVED", "DISAGREES"):
                assessment = "mismatch"
            else:
                assessment = "unknown"
            expected = x.get("expected") or x.get("recorded")
            if isinstance(expected, (dict, list)):
                expected = json.dumps(expected, sort_keys=True)
            check = {
                "label": label,
                "kind": kind,
                "variant": desc["design"],
                "expect": str(expected) if expected else None,
            }
            checks[label] = check
            row = {
                **check,
                "concern": name,
                "run_id": run_id,
                "outcome": outcome,
                "assessment": assessment,
                "receipt_path": relative(p),
            }
            for key in ("verified", "errors"):
                if isinstance(obs.get(key), int):
                    row[key] = obs[key]
            if isinstance(x.get("comparisons"), int):
                row["cases"] = x["comparisons"]
            rows.append(row)
        for c in config.get("controls", []):
            if isinstance(c, dict) and c.get("name"):
                checks.setdefault(
                    c["name"],
                    {
                        "label": c["name"],
                        "kind": "control",
                        "expect": "named failing obligation",
                    },
                )
        if config.get("expected_verified") is not None:
            checks.setdefault(
                "proof",
                {
                    "label": "proof",
                    "kind": "proof",
                    "expect": f"{config['expected_verified']} verified",
                },
            )
        title = name.replace("_", " ").replace("-", " ")
        write_json(
            folder / "manifest.json",
            {
                "title": title,
                "question": desc["scope"],
                "ontology_ids": sorted(owners[name]),
                "runs": list(checks.values()),
            },
        )
        body = [
            f"# {title}",
            desc["scope"],
            "Evidence status: " + desc["status"] + ". Variant: " + desc["design"] + ".",
            "Verified and errors count obligations reported by the verifier. A control is judged against its named expected failure. Native observations have their recorded scope.",
        ]
        formal = source / config["root"] if config.get("root") else source
        for target, label in [
            (formal, "Formal source"),
            (notes, "Formal claims, product bindings and limitations"),
            (REPO_ROOT / desc.get("premises file", ""), "Premises"),
            (
                VERIFICATION_DIR / "crosswalk/decision-links.tsv",
                "Product and declaration crosswalk",
            ),
        ]:
            if target.exists() and target != REPO_ROOT:
                body.append(link(folder, target, label))
        (folder / "BINDINGS.md").write_text("\n\n".join(body) + "\n")
    latest = {}
    for row in rows:
        key = (row["concern"], row["label"])
        previous = latest.get(key)
        if previous is None or row["run_id"] >= previous["run_id"]:
            latest[key] = row
    rows = list(latest.values())
    (VERIFICATION_DIR / "results/viewer-index.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    )
    print(f"{len(families)} concerns, {len(rows)} saved verification rows")


if __name__ == "__main__":
    build()
