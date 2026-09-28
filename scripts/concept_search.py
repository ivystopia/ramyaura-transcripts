"""Search curated editorial concept annotations using only the saved Ramy corpus."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
CHANNEL_ID = "UChk2Zu5h5yJ9BBD4VS-_chQ"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def normalise(value):
    return " ".join(re.sub(r"[-–—]", " ", value.casefold()).split())


def load(root=ROOT):
    catalogue = json.loads((root / "data/concepts.json").read_text())
    annotations = [json.loads(line) for line in (root / "data/concept-annotations.jsonl").read_text().splitlines()]
    passages = {r["chunk_key"]: r for r in map(json.loads, (root / "data/corpus.jsonl").read_text().splitlines())}
    sources = {r["video_id"]: r for r in map(json.loads, (root / "data/sources.jsonl").read_text().splitlines())}
    validate(catalogue, annotations, passages, sources, (root / "GLOSSARY.md").read_text())
    return catalogue, annotations, passages, sources


def validate(catalogue, annotations, passages, sources, glossary):
    require(set(catalogue) == {"schema_version", "editorial_author", "editorial_basis", "review_scope", "concepts"}, "Unexpected concept catalogue fields")
    require(catalogue["schema_version"] == 1 and catalogue["editorial_author"] == "assistant", "Unexpected concept provenance")
    concepts = {c["id"]: c for c in catalogue["concepts"]}
    require(len(concepts) == len(catalogue["concepts"]), "Duplicate concept IDs")
    aliases = {}
    for cid, concept in concepts.items():
        require(set(concept) == {"id", "label", "aliases", "glossary_anchor", "definition", "related"}, "Unexpected concept fields")
        require(re.fullmatch(r"[a-z][a-z0-9-]*", cid), "Invalid concept ID")
        require(f'id="{concept["glossary_anchor"]}"' in glossary, "Missing concept glossary anchor")
        require(all(c in concepts and c != cid for c in concept["related"]), "Unknown related concept")
        for alias in [cid, concept["label"], *concept["aliases"]]:
            key = normalise(alias)
            require(key and aliases.get(key, cid) == cid, "Ambiguous concept alias")
            aliases[key] = cid
    ids = set()
    required = {"id", "concept_id", "chunk_key", "text_sha256", "span", "classification", "interpretation", "conditions", "context_keys", "context_text_sha256", "confidence", "review_status", "human_reviewed", "recording_patch", "current_patch_applicability"}
    for item in annotations:
        require(required <= set(item) <= required | {"decision"}, "Unexpected editorial annotation fields")
        require(item["id"] not in ids, "Duplicate annotation ID")
        ids.add(item["id"])
        require(item["concept_id"] in concepts, "Unknown annotation concept")
        require(item["classification"] in {"supports", "exclude", "unresolved"}, "Invalid concept classification")
        require(item["confidence"] in {"high", "medium", "low"}, "Invalid annotation confidence")
        require(item["review_status"] == "assistant_context_review_not_audio_verification" and item["human_reviewed"] is False, "Unreviewed authorship promotion")
        require(item["recording_patch"] is None and item["current_patch_applicability"] == "unvalidated", "Unreviewed concept patch promotion")
        require(isinstance(item["interpretation"], str) and item["interpretation"].strip(), "Missing editorial interpretation")
        require(isinstance(item["conditions"], list) and all(isinstance(c, str) for c in item["conditions"]), "Invalid conditions")
        require(isinstance(item["context_keys"], list) and len(set(item["context_keys"])) == len(item["context_keys"]), "Invalid context references")
        require(isinstance(item["context_text_sha256"], dict) and set(item["context_text_sha256"]) == set(item["context_keys"]), "Missing continuation hashes")
        key = item["chunk_key"]
        require(key in passages, "Editorial annotation has no published passage")
        passage = passages[key]
        require(passage["video_id"] in sources and sources[passage["video_id"]]["channel_id"] == CHANNEL_ID, "Concept evidence must be from the published RamyAura channel")
        digest = hashlib.sha256(passage["text"].encode()).hexdigest()
        require(item["text_sha256"] == passage["text_sha256"] == digest, "Stale editorial annotation: source text changed")
        span = item["span"]
        require(isinstance(span, list) and len(span) == 2 and all(type(x) is int for x in span), "Invalid editorial text span")
        require(0 <= span[0] < span[1] <= len(passage["text"]), "Editorial span outside passage")
        for context_key in item["context_keys"]:
            require(context_key != key and context_key in passages and passages[context_key]["video_id"] == passage["video_id"], "Invalid continuation passage")
            context = passages[context_key]
            require(item["context_text_sha256"][context_key] == context["text_sha256"] == hashlib.sha256(context["text"].encode()).hexdigest(), "Stale continuation: context text changed")
        if "decision" in item:
            require(set(item["decision"]) == {"situation", "goal", "considered_action", "chosen_action", "reason", "qualification"}, "Unexpected decision fields")
            require(all(isinstance(v, str) and v.strip() for v in item["decision"].values()), "Incomplete decision context")
    return aliases


def resolve(catalogue, query):
    target = normalise(query)
    for concept in catalogue["concepts"]:
        if target in {normalise(a) for a in [concept["id"], concept["label"], *concept["aliases"]]}:
            return concept
    raise ValueError("Unknown concept; use --list for the curated catalogue")


def search(dataset, query, all_classifications=False):
    catalogue, annotations, passages, sources = dataset
    concept = resolve(catalogue, query)

    def evidence(key, span=None):
        r = passages[key]
        s = sources[r["video_id"]]
        start, end = span or [0, len(r["text"])]
        encounters = [e for e in s["encounters"] if r["start_seconds"] >= e["start"] and r["end_seconds"] <= e["end"]]
        return dict(chunk_key=key, video_id=r["video_id"], title=s["title"], upload_date=s["upload_date"],
                    source_url=r["source_url"], transcript_link=f'{s["transcript_path"]}#p-{key}',
                    start_seconds=r["start_seconds"], end_seconds=r["end_seconds"], timing_method=r["timing_method"],
                    quality_flags=r["quality_flags"], excerpt=r["text"][start:end],
                    encounters=[{"opponent": e["name"], "role": e["role"]} for e in encounters],
                    recording_patch=r["recording_patch"], current_patch_applicability=r["current_patch_applicability"])

    results = []
    for item in annotations:
        if item["concept_id"] != concept["id"] or (not all_classifications and item["classification"] != "supports"):
            continue
        results.append(dict(annotation=item, evidence=evidence(item["chunk_key"], item["span"]),
                            context=[evidence(k) for k in item["context_keys"]]))
    results.sort(key=lambda r: (r["evidence"]["upload_date"], r["evidence"]["video_id"], -r["evidence"]["start_seconds"]), reverse=True)
    return {"concept": concept, "coverage": catalogue["review_scope"], "total": len(results), "results": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="?")
    parser.add_argument("--list", action="store_true", help="List curated concepts and aliases")
    parser.add_argument("--json", action="store_true", help="Emit structured results including evidence and context")
    parser.add_argument("--all-classifications", action="store_true", help="Also show explicitly excluded and unresolved matches")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    if args.limit < 1 or (not args.query and not args.list):
        parser.error("Supply a concept or --list, and a positive --limit")
    try:
        dataset = load()
        if args.list:
            if args.json:
                print(json.dumps(dataset[0], ensure_ascii=False, indent=2))
            else:
                print(dataset[0]["review_scope"])
                for c in dataset[0]["concepts"]:
                    print(f'{c["id"]}: {c["label"]} ({", ".join(c["aliases"])})')
            return
        result = search(dataset, args.query, args.all_classifications)
    except (ValueError, KeyError) as error:
        parser.error(str(error))
    result["results"] = result["results"][:args.limit]
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    print(result["concept"]["label"] + ": " + result["concept"]["definition"])
    print(result["coverage"])
    print(f'Showing {len(result["results"])} of {result["total"]} annotated matches. Recording patches remain unvalidated.')
    for match in result["results"]:
        a, e = match["annotation"], match["evidence"]
        print(f'\n[{a["classification"]}] {e["title"]} · uploaded {e["upload_date"]}')
        print(e["source_url"])
        print("Recorded roles: " + (", ".join(x["role"] for x in e["encounters"]) or "unknown / transition"))
        print(f'Approximate interval: {e["start_seconds"]}–{e["end_seconds"]} seconds. {e["timing_method"]}')
        print("Editorial interpretation: " + a["interpretation"])
        print("Transcript excerpt: " + e["excerpt"])
        for context in match["context"]:
            print("Linked context: " + context["source_url"])
            print(context["excerpt"])
        if a["conditions"]:
            print("Conditions: " + "; ".join(a["conditions"]))
        if "decision" in a:
            for label, value in a["decision"].items():
                print(label.replace("_", " ").capitalize() + ": " + value)


if __name__ == "__main__":
    main()
