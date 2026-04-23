from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from Config import config
from main import main


def parse_args():
    parser = argparse.ArgumentParser(description="Run Linear benchmark cases in parallel.")
    parser.add_argument(
        "--workers",
        type=int,
        default=5,
        help="Number of worker threads to use. Default: 5.",
    )
    parser.add_argument(
        "--cases",
        nargs="*",
        default=None,
        help="Optional case names to run, e.g. `test 1 2`.",
    )
    parser.add_argument(
        "--result-path",
        default=None,
        help="Optional override for Config.resultpath.",
    )
    return parser.parse_args()


def normalize_case_name(case_name: str) -> str:
    return Path(case_name).stem


def case_sort_key(case_name: str):
    if case_name.isdigit():
        return (0, int(case_name))
    return (1, case_name)


def is_case_completed(result_dir: Path, case_name: str) -> bool:
    result_file = result_dir / f"{case_name}.json"
    if not result_file.exists():
        return False
    try:
        payload = json.loads(result_file.read_text())
    except (OSError, json.JSONDecodeError):
        return False
    return bool(payload.get("answer")) and bool(payload.get("verification_result"))


def build_case_paths(case_name: str):
    return (
        Path("Benchmarks/Linear/c") / f"{case_name}.c",
        Path("Benchmarks/Linear/c_graph") / f"{case_name}.c.json",
        Path("Benchmarks/Linear/c_smt2") / f"{case_name}.c.smt",
    )


def run_case(case_name: str):
    path_c, path_g, path_s = build_case_paths(case_name)
    missing_paths = [str(path) for path in (path_c, path_g, path_s) if not path.exists()]
    if missing_paths:
        return case_name, False, f"missing files: {', '.join(missing_paths)}"

    time_used, answer, gpt_answer, iteration = main(
        str(path_c),
        str(path_g),
        str(path_s),
        case_name,
    )
    if answer is None:
        return case_name, False, "no result"
    return case_name, True, f"time={time_used}, proposals={iteration}, answer={answer}"


def discover_cases(selected_cases: list[str] | None):
    benchmark_dir = Path("Benchmarks/Linear/c")
    all_cases = sorted(
        [path.stem for path in benchmark_dir.glob("*.c")],
        key=case_sort_key,
    )
    if not selected_cases:
        return all_cases

    requested_cases = [normalize_case_name(case_name) for case_name in selected_cases]
    requested_set = set(requested_cases)
    return [case_name for case_name in all_cases if case_name in requested_set]


def main_parallel():
    args = parse_args()
    if args.workers < 1:
        raise ValueError("--workers must be >= 1")
    if args.result_path:
        config.resultpath = args.result_path

    result_dir = Path("Result") / config.resultpath
    result_dir.mkdir(parents=True, exist_ok=True)

    all_cases = discover_cases(args.cases)
    pending_cases = [
        case_name for case_name in all_cases
        if not is_case_completed(result_dir, case_name)
    ]

    print(f"Result path: {config.resultpath}")
    print(f"Discovered cases: {len(all_cases)}")
    print(f"Already completed: {len(all_cases) - len(pending_cases)}")
    print(f"Pending cases: {len(pending_cases)}")

    if not pending_cases:
        print("No pending cases. Nothing to run.")
        return

    success_count = 0
    failure_count = 0
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_to_case = {
            executor.submit(run_case, case_name): case_name
            for case_name in pending_cases
        }
        for future in as_completed(future_to_case):
            case_name = future_to_case[future]
            try:
                _, success, detail = future.result()
            except Exception as exc:
                success = False
                detail = str(exc)

            if success:
                success_count += 1
                print(f"[SUCCESS] {case_name}: {detail}")
            else:
                failure_count += 1
                print(f"[FAILED] {case_name}: {detail}")

    print(f"Finished. Success: {success_count}, Failed: {failure_count}")


if __name__ == "__main__":
    main_parallel()
