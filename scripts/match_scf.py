#!/usr/bin/env python3
"""
Match JSON entries to CSV rows by text similarity and write an updated JSON.

Similarity is computed between:
- JSON side: "Raw Error Text" + "Explanation"
- CSV side: columns 1, 2, and 4 (1-based positions)

By default, all 5 CSV columns are copied into the output under "SCF_Match.csv_fields".

Usage:
  python match_scf.py --in-json out_full.json --in-csv SCF_descriptions.csv --out-json out_updated.json
Optional flags:
  --min-sim 0.05               # threshold for low_confidence flag
  --use-char-ngrams            # include character n-grams (3,5) in addition to word n-grams (1,2)
  --no-stopwords               # do NOT drop a small built-in list of English stopwords
  --no-headers                 # treat CSV as 5 positional columns without a header row
  --report path/to/report.csv  # write a QA report with top match per JSON entry
  --dry-run                    # compute and print summary but do not write out_json
"""

import argparse
import csv
import json
import math
import os
import re
import sys
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple

# Third-party (widely available)
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    from scipy.sparse import hstack
except Exception as e:
    sys.stderr.write("ERROR: This script requires scikit-learn and scipy.\n")
    sys.stderr.write("Install with: pip install scikit-learn scipy\n")
    raise


DEFAULT_STOPWORDS = {
    "a","an","and","are","as","at","be","but","by","for","if","in","into","is","it",
    "no","not","of","on","or","such","that","the","their","then","there","these",
    "they","this","to","was","will","with","from","we","you","your","i","our"
}

CLEAN_RE = re.compile(r"[^0-9a-zA-Z\s]+", flags=re.UNICODE)


def clean_text(text: str, drop_stopwords: bool = True) -> str:
    if text is None:
        return ""
    t = text.lower()
    t = t.replace("\\n", " ").replace("\n", " ").replace("\r", " ")
    t = CLEAN_RE.sub(" ", t)
    t = re.sub(r"\s+", " ", t).strip()
    if drop_stopwords:
        tokens = [w for w in t.split() if w not in DEFAULT_STOPWORDS]
        t = " ".join(tokens)
    return t


def concat_json_fields(entry: Dict[str, Any]) -> str:
    ret = []
    for key in ["Raw Error Text", "Explanation"]:
        if key in entry and entry[key]:
            ret.append(str(entry[key]))
    return " [SEP] ".join(ret).strip()


def concat_csv_fields(row: Dict[str, Any], use_headers: bool, header_map: List[str]) -> str:
    # Use columns 1,2,4 (1-based) => indices 0,1,3.
    vals = []
    if use_headers:
        for idx in (0,1,3):
            if idx < len(header_map):
                k = header_map[idx]
                vals.append(str(row.get(k, "")).strip())
            else:
                vals.append("")
    else:
        # Positional keys "col_1"...
        for idx in (1,2,4):
            vals.append(str(row.get(f"col_{idx}", "")).strip())
    return " [SEP] ".join(vals).strip()


def token_overlap_score(a: str, b: str) -> int:
    sa = set(a.split())
    sb = set(b.split())
    return len(sa & sb)


@dataclass
class MatchResult:
    csv_index: int
    similarity: float
    low_confidence: bool
    overlap: int


def build_vectorizer(use_char: bool, drop_stopwords: bool):
    word_vec = TfidfVectorizer(ngram_range=(1,2), analyzer="word", lowercase=False, min_df=1)
    if use_char:
        char_vec = TfidfVectorizer(ngram_range=(3,5), analyzer="char", lowercase=False, min_df=1)
        return word_vec, char_vec
    return word_vec, None


def vectorize_corpus(json_texts: List[str], csv_texts: List[str], use_char: bool, drop_stopwords: bool):
    # Pre-clean both sides with the same pipeline
    J = [clean_text(t, drop_stopwords=drop_stopwords) for t in json_texts]
    C = [clean_text(t, drop_stopwords=drop_stopwords) for t in csv_texts]

    word_vec, char_vec = build_vectorizer(use_char, drop_stopwords)

    # Fit on union to share vocabulary space; then split
    union = J + C
    X_word = word_vec.fit_transform(union)
    XJ_word = X_word[:len(J), :]
    XC_word = X_word[len(J):, :]

    if char_vec is not None:
        X_char = char_vec.fit_transform(union)
        XJ_char = X_char[:len(J), :]
        XC_char = X_char[len(J):, :]
        XJ = hstack([XJ_word, XJ_char])
        XC = hstack([XC_word, XC_char])
    else:
        XJ, XC = XJ_word, XC_word

    return J, C, XJ, XC


def read_json(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("Input JSON must be a list of entries.")
    return data


def read_csv(path: str, no_headers: bool) -> Tuple[List[Dict[str, Any]], List[str], bool]:
    rows = []
    header_map = []
    use_headers = not no_headers
    with open(path, "r", encoding="utf-8", newline="") as f:
        if use_headers:
            reader = csv.DictReader(f)
            header_map = list(reader.fieldnames or [])
            for r in reader:
                rows.append(r)
            # Validate that there are at least 5 columns
            if len(header_map) < 5:
                raise ValueError("CSV appears to have fewer than 5 columns with headers.")
        else:
            reader = csv.reader(f)
            for r in reader:
                # Expect 5 columns, pad or trim as necessary
                vals = list(r)[:5]
                while len(vals) < 5:
                    vals.append("")
                rows.append({f"col_{i+1}": vals[i] for i in range(5)})
            header_map = [f"col_{i+1}" for i in range(5)]
    return rows, header_map, use_headers


def collect_csv_fields(row: Dict[str, Any], use_headers: bool, header_map: List[str]) -> Dict[str, Any]:
    if use_headers:
        result = {}
        # Copy first five columns only, preserving given order
        for i in range(min(5, len(header_map))):
            k = header_map[i]
            result[k] = row.get(k, "")
        # If fewer than 5 in header_map, pad with col_i keys
        for i in range(len(header_map), 5):
            result[f"col_{i+1}"] = ""
        return result
    else:
        return {f"col_{i+1}": row.get(f"col_{i+1}", "") for i in range(5)}


def main():
    ap = argparse.ArgumentParser(description="Match JSON entries to CSV rows using TF-IDF cosine similarity.")
    ap.add_argument("--in-json", required=True, help="Path to input JSON (list of entries).")
    ap.add_argument("--in-csv", required=True, help="Path to input CSV (5 columns).")
    ap.add_argument("--out-json", required=True, help="Path to write updated JSON.")
    ap.add_argument("--min-sim", type=float, default=0.05, help="Low-confidence threshold (default: 0.05).")
    ap.add_argument("--use-char-ngrams", action="store_true", help="Include character n-grams (3,5) in similarity.")
    ap.add_argument("--no-stopwords", action="store_true", help="Do NOT drop a small built-in stopword list.")
    ap.add_argument("--no-headers", action="store_true", help="Treat CSV as positional 5 columns (no header row).")
    ap.add_argument("--report", default=None, help="Optional path to write a QA CSV report.")
    ap.add_argument("--dry-run", action="store_true", help="Compute only; do not write out_json.")
    args = ap.parse_args()

    json_entries = read_json(args.in_json)
    csv_rows, header_map, use_headers = read_csv(args.in_csv, no_headers=args.no_headers)

    # Build concatenated texts
    json_texts = [concat_json_fields(e) for e in json_entries]
    csv_texts = [concat_csv_fields(r, use_headers, header_map) for r in csv_rows]

    # Vectorize and compute similarity
    J_clean, C_clean, XJ, XC = vectorize_corpus(
        json_texts, csv_texts,
        use_char=args.use_char_ngrams,
        drop_stopwords=not args.no_stopwords
    )

    sim_matrix = cosine_similarity(XJ, XC)  # shape M x N

    # For each JSON entry, select best CSV match
    matches: List[MatchResult] = []
    for i in range(sim_matrix.shape[0]):
        row = sim_matrix[i]
        # Candidate indices with max similarity
        max_sim = float(row.max()) if row.size else 0.0
        idxs = [j for j, v in enumerate(row) if abs(v - max_sim) < 1e-12]

        # Tie-break using token overlap
        if len(idxs) > 1:
            overlaps = [token_overlap_score(J_clean[i], C_clean[j]) for j in idxs]
            best = idxs[overlaps.index(max(overlaps))]
            overlap_val = max(overlaps)
        else:
            best = idxs[0] if idxs else -1
            overlap_val = token_overlap_score(J_clean[i], C_clean[best]) if best >= 0 else 0

        low_conf = (max_sim < args.min_sim)
        matches.append(MatchResult(csv_index=best, similarity=max_sim, low_confidence=low_conf, overlap=overlap_val))

    # Update JSON entries
    updated = []
    for i, entry in enumerate(json_entries):
        m = matches[i]
        obj = dict(entry)  # shallow copy
        if 0 <= m.csv_index < len(csv_rows):
            csv_row = csv_rows[m.csv_index]
            csv_fields = collect_csv_fields(csv_row, use_headers, header_map)
        else:
            csv_fields = { (header_map[k] if k < len(header_map) else f"col_{k+1}") : "" for k in range(5) }
        obj["SCF_Match"] = {
            "matched_row_index": int(m.csv_index),
            "similarity": float(m.similarity),
            "low_confidence": bool(m.low_confidence),
            "csv_fields": csv_fields
        }
        updated.append(obj)

    # Optional report
    if args.report:
        try:
            with open(args.report, "w", encoding="utf-8", newline="") as rf:
                writer = csv.writer(rf)
                writer.writerow(["json_index", "csv_index", "similarity", "low_confidence",
                                 "json_text_snippet", "csv_text_snippet"])
                for i, m in enumerate(matches):
                    j_snip = (json_texts[i] or "")[:200].replace("\n", " ")
                    c_snip = (csv_texts[m.csv_index] or "")[:200].replace("\n", " ") if 0 <= m.csv_index < len(csv_texts) else ""
                    writer.writerow([i, m.csv_index, f"{m.similarity:.6f}", m.low_confidence, j_snip, c_snip])
        except Exception as e:
            sys.stderr.write(f"WARNING: Could not write report to {args.report}: {e}\n")

    # Summary
    sims = [m.similarity for m in matches if not math.isnan(m.similarity)]
    if sims:
        avg = sum(sims) / len(sims)
        low = sum(1 for m in matches if m.low_confidence)
        print(f"[Summary] JSON entries: {len(matches)} | CSV rows: {len(csv_rows)} | "
              f"avg_sim={avg:.4f} | low_conf={low}")
    else:
        print(f"[Summary] No similarities computed. JSON entries: {len(matches)}, CSV rows: {len(csv_rows)}")

    # Write output
    if not args.dry_run:
        out_path = args.out_json
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as wf:
            json.dump(updated, wf, ensure_ascii=False, indent=2)
        print(f"Wrote updated JSON to: {out_path}")


if __name__ == "__main__":
    main()
