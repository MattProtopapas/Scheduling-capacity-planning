"""Shared constants and data model for the scheduling and capacity planning tool.

Used by generate_data.py, validate_data.py, and analyze_schedule.py so all
three scripts agree on what a valid job record looks like.

All times are in working hours on a single shared clock that starts at 0.
"""

from pydantic import BaseModel, ConfigDict, Field, model_validator

PRODUCT_FAMILIES = ["Cabinets", "Doors", "Frames", "Panels", "Shelving", "Worktops"]

HOURS_PER_WEEK = 40

RAW_DATA_PATH = "data/jobs_raw.csv"
VALIDATED_DATA_PATH = "data/jobs_validated.csv"
VALIDATION_REPORT_PATH = "data/validation_report.txt"
OUTPUT_WORKBOOK_PATH = "output/schedule_analysis.xlsx"
OUTPUT_GANTT_PATH = "output/gantt.png"

CSV_FIELDS = [
    "job_id",
    "customer",
    "product_family",
    "processing_hours",
    "release_hour",
    "due_hour",
    "order_value",
]


class Job(BaseModel):
    """A single order to be produced on one machine (or crew)."""

    model_config = ConfigDict(extra="ignore")

    job_id: str = Field(min_length=1)
    customer: str = Field(min_length=1)
    product_family: str = Field(min_length=1)
    processing_hours: float = Field(gt=0)
    release_hour: float = Field(ge=0)
    due_hour: float = Field(gt=0)
    order_value: float = Field(gt=0)

    @model_validator(mode="after")
    def check_times(self):
        if self.due_hour < self.release_hour + self.processing_hours:
            raise ValueError("due_hour is earlier than release_hour + processing_hours (job can never be on time)")
        return self
