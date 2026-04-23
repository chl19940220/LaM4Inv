from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Summarize benchmark result JSON files.")
    parser.add_argument(
        "--input-dir",
        default="Result/Gemini_Results",
        help="Directory containing per-case JSON result files.",
    )
    parser.add_argument(
        "--output-file",
        default=None,
        help="Path to write the summary JSON. Defaults to <input-dir>/summary.json.",
    )
    return parser.parse_args()


def case_sort_key(case_name: str):
    if case_name.isdigit():
        return (0, int(case_name))
    return (1, case_name)


def is_result_file(path: Path) -> bool:
    return path.suffix == ".json" and path.stem != "summary"


def main():
    args = parse_args()
    input_dir = Path(args.input_dir)
    output_file = Path(args.output_file) if args.output_file else input_dir / "summary.json"

    result_files = sorted(
        [path for path in input_dir.iterdir() if path.is_file() and is_result_file(path)],
        key=lambda path: case_sort_key(path.stem),
    )

    true_cases: list[str] = []
    false_cases: list[str] = []
    invalid_files: list[str] = []
    total_llm_tokens = 0
    total_time_cost = 0.0
    total_smt_time = 0.0

    for result_file in result_files:
        try:
            payload = json.loads(result_file.read_text())
        except (OSError, json.JSONDecodeError):
            invalid_files.append(result_file.name)
            continue

        case_name = str(payload.get("case_name", result_file.stem))
        verification_result = bool(payload.get("verification_result"))
        if verification_result:
            true_cases.append(case_name)
        else:
            false_cases.append(case_name)

        total_llm_tokens += int(payload.get("llm_total_tokens", 0) or 0)
        total_time_cost += float(payload.get("time_cost", 0.0) or 0.0)
        total_smt_time += float(payload.get("smt_total_time", 0.0) or 0.0)

    summary = {
        "input_dir": str(input_dir),
        "total_files": len(result_files),
        "valid_files": len(result_files) - len(invalid_files),
        "invalid_files": invalid_files,
        "verification_result_counts": {
            "true": len(true_cases),
            "false": len(false_cases),
        },
        "false_cases": sorted(false_cases, key=case_sort_key),
        "total_llm_tokens": total_llm_tokens,
        "total_time_cost": total_time_cost,
        "total_smt_time": total_smt_time,
    }

    output_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(f"Summary written to {output_file}")


if __name__ == "__main__":
    main()
