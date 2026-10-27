"""Generate a fake job (order) dataset with Faker.

Produces a CSV of jobs (processing time, release time, due date, order value)
that the rest of the pipeline (validate_data.py, analyze_schedule.py)
consumes. Processing times are scaled so the jobs fill --target-load of the
available machine hours, which is what makes sequencing matter: at ~90% load
a bad dispatching rule produces plenty of late orders. A small percentage of
rows are deliberately corrupted (negative hours, impossible due dates, blanks,
duplicate IDs) so validate_data.py has real work to do - pass --error-rate 0
for a perfectly clean dataset.
"""

import argparse
import csv
import os
import random

from faker import Faker

from scheduling_common import CSV_FIELDS, HOURS_PER_WEEK, PRODUCT_FAMILIES, RAW_DATA_PATH


def generate_dataset(
    count: int, error_rate: float, seed: int | None, machines: int, weeks: int, target_load: float
) -> list[dict]:
    if seed is not None:
        random.seed(seed)
        Faker.seed(seed)
    fake = Faker()

    horizon = weeks * HOURS_PER_WEEK
    capacity = machines * horizon

    # Draw raw processing times, then rescale so the jobs fill target_load of total capacity.
    raw = [random.uniform(1, 12) for _ in range(count)]
    scale = target_load * capacity / sum(raw)
    processing = [max(0.5, round(p * scale * 2) / 2) for p in raw]  # nearest half hour

    customers = [fake.company() for _ in range(max(5, count // 6))]

    rows = []
    for i, proc in enumerate(processing, start=1):
        release = round(random.uniform(0, horizon * 0.8), 1)
        # Due date = release + processing + a random allowance; some orders are tight, some relaxed.
        allowance = random.choice([0.5, 1.0, 1.5, 2.5, 4.0]) * proc + random.uniform(0, 10)
        rows.append(
            {
                "job_id": f"JOB-{i:04d}",
                "customer": random.choice(customers),
                "product_family": random.choice(PRODUCT_FAMILIES),
                "processing_hours": proc,
                "release_hour": release,
                "due_hour": round(release + proc + allowance, 1),
                "order_value": round(proc * random.uniform(60, 140), 2),
            }
        )

    n_errors = round(count * error_rate)
    for row in random.sample(rows, k=min(n_errors, count)):
        corrupt_row(row)

    # Inject a duplicate job ID to exercise the validator's duplicate check.
    if error_rate > 0 and count > 1:
        dup = dict(rows[0])
        dup["job_id"] = rows[-1]["job_id"]
        rows.append(dup)

    return rows


def corrupt_row(row: dict) -> dict:
    """Introduce one realistic data-quality issue into a row, in place."""
    issue = random.choice(["negative_hours", "due_before_release", "blank_customer", "zero_value", "blank_hours"])
    if issue == "negative_hours":
        row["processing_hours"] = -abs(row["processing_hours"])
    elif issue == "due_before_release":
        row["due_hour"] = max(row["release_hour"] - 5, 0.1)
    elif issue == "blank_customer":
        row["customer"] = ""
    elif issue == "zero_value":
        row["order_value"] = 0
    elif issue == "blank_hours":
        row["processing_hours"] = ""
    return row


def write_csv(rows: list[dict], path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate fake job data for the scheduling pipeline.")
    parser.add_argument("--count", type=int, default=60, help="Number of jobs to generate (default: 60)")
    parser.add_argument(
        "--error-rate",
        type=float,
        default=0.05,
        help="Fraction of rows (0-1) to deliberately corrupt, to exercise validate_data.py (default: 0.05)",
    )
    parser.add_argument("--machines", type=int, default=3, help="Machines/crews the load is sized for (default: 3)")
    parser.add_argument("--weeks", type=int, default=4, help="Planning horizon in 40-hour weeks (default: 4)")
    parser.add_argument(
        "--target-load", type=float, default=0.9, help="Share of total machine hours the jobs should fill (default: 0.9)"
    )
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducible output")
    parser.add_argument("--output", type=str, default=RAW_DATA_PATH, help="Path to write the raw CSV to")
    args = parser.parse_args()

    rows = generate_dataset(args.count, args.error_rate, args.seed, args.machines, args.weeks, args.target_load)
    write_csv(rows, args.output)
    print(f"Generated {len(rows)} rows ({round(args.error_rate * 100)}% target error rate) -> {args.output}")


if __name__ == "__main__":
    main()
