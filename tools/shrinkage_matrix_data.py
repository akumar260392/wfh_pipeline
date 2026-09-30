import json
from typing import Any, Dict, List, Optional, Union
import pandas as pd


def generate_shrinkage_matrix_table(
    schedule_summary_payload: Union[str, Dict[str, Any]],
    assumptions_input: Optional[Dict[str, float]] = None,
    as_dataframe: bool = True,
) -> Union[pd.DataFrame, List[Dict[str, Any]]]:
    """Generates the wide WFM Shrinkage Planning Table matching the exact Excel formulas.

    Major sections:
      - Current: C5 to G5 (from schedule summary metrics % of scheduled)
      - Assumption: H5 to L5 (input or default values)
      - Plan: M5 to Q5 (=IF(Assumption > Current, Assumption, Current))
      - % To be added to plan: R5 to V5 (=Plan - Current)
      - Hours reduction: W5 to AA5 (=(% To be added) * Scheduled)
    """
    if isinstance(schedule_summary_payload, str):
        try:
            data = json.loads(schedule_summary_payload)
        except Exception:
            data = {}
    else:
        data = schedule_summary_payload

    daily_totals_list = data.get("Daily Totals Summary", [])
    metrics_pct_list = data.get("Metrics as % of Scheduled Hours", [])

    # The 4 base sub-categories (N5:Q5)
    base_sub_categories = [
        "PLANNED ABSENCE",
        "ABSENCE",
        "HOLIDAY PAID",
        "HOLIDAY UNPAID",
    ]

    # Default assumptions (as decimals: 20% = 0.20, 6% = 0.06)
    default_assumptions = {
        "PLANNED ABSENCE": 0.0,
        "ABSENCE": 0.20,
        "HOLIDAY PAID": 0.06,
        "HOLIDAY UNPAID": 0.0,
    }
    assumptions_config = {**default_assumptions, **(assumptions_input or {})}

    def _lookup(source: dict, key: str) -> float:
        norm = key.strip().lower()
        for k, v in source.items():
            if str(k).strip().lower() == norm:
                try:
                    return float(v) if v is not None else 0.0
                except (ValueError, TypeError):
                    return 0.0
        return 0.0

    rows = []

    for dt, dp in zip(daily_totals_list, metrics_pct_list):
        date_str = dt.get("Date")
        scheduled_hours = _lookup(dt, "Scheduled")

        # -------------------------------------------------------------
        # 1. Current (C5:G5) - Decimals from "Metrics as % of Scheduled Hours"
        # -------------------------------------------------------------
        current_sub = {cat: _lookup(dp, cat) for cat in base_sub_categories}
        current_total = _lookup(dp, "OUT OF OFFICE SHRINKAGE")
        if current_total == 0.0:
            current_total = sum(current_sub.values())

        # -------------------------------------------------------------
        # 2. Assumption (H5:L5)
        # -------------------------------------------------------------
        assumption_sub = {
            cat: assumptions_config.get(cat, 0.0) for cat in base_sub_categories
        }
        assumption_total = sum(assumption_sub.values())  # SUM(I5:L5)

        # -------------------------------------------------------------
        # 3. Plan (M5:Q5)
        # Formula: =IF(I5 > D5, I5, D5) -> max(Assumption, Current)
        # -------------------------------------------------------------
        plan_sub = {
            cat: max(assumption_sub[cat], current_sub[cat])
            for cat in base_sub_categories
        }
        plan_total = sum(plan_sub.values())  # =SUM(N5:Q5)

        # -------------------------------------------------------------
        # 4. % To be added to plan (R5:V5)
        # Formula: =Plan - Current
        # -------------------------------------------------------------
        to_add_sub = {
            cat: round(plan_sub[cat] - current_sub[cat], 4)
            for cat in base_sub_categories
        }
        to_add_total = round(sum(to_add_sub.values()), 4)  # =SUM(S5:V5)

        # -------------------------------------------------------------
        # 5. Hours Reduction (W5:AA5)
        # Formula: =(% To be added) * Scheduled ($C5)
        # -------------------------------------------------------------
        hours_red_sub = {
            cat: round(to_add_sub[cat] * scheduled_hours, 2)
            for cat in base_sub_categories
        }
        hours_red_total = round(
            sum(hours_red_sub.values()), 2
        )  # =SUM(X5:AA5)

        # Build complete row record
        row_dict = {
            ("Meta", "Date"): date_str,
            ("Meta", "Scheduled"): scheduled_hours,
            # Current (C5:G5)
            ("Current", "OUT OF OFFICE SHRINKAGE"): round(current_total, 4),
            ("Current", "PLANNED ABSENCE"): round(
                current_sub["PLANNED ABSENCE"], 4
            ),
            ("Current", "ABSENCE"): round(current_sub["ABSENCE"], 4),
            ("Current", "HOLIDAY PAID"): round(
                current_sub["HOLIDAY PAID"], 4
            ),
            ("Current", "HOLIDAY UNPAID"): round(
                current_sub["HOLIDAY UNPAID"], 4
            ),
            # Assumption (H5:L5)
            ("Assumption", "OUT OF OFFICE SHRINKAGE"): round(
                assumption_total, 4
            ),
            ("Assumption", "PLANNED ABSENCE"): round(
                assumption_sub["PLANNED ABSENCE"], 4
            ),
            ("Assumption", "ABSENCE"): round(assumption_sub["ABSENCE"], 4),
            ("Assumption", "HOLIDAY PAID"): round(
                assumption_sub["HOLIDAY PAID"], 4
            ),
            ("Assumption", "HOLIDAY UNPAID"): round(
                assumption_sub["HOLIDAY UNPAID"], 4
            ),
            # Plan (M5:Q5)
            ("Plan", "OUT OF OFFICE SHRINKAGE"): round(plan_total, 4),
            ("Plan", "PLANNED ABSENCE"): round(plan_sub["PLANNED ABSENCE"], 4),
            ("Plan", "ABSENCE"): round(plan_sub["ABSENCE"], 4),
            ("Plan", "HOLIDAY PAID"): round(plan_sub["HOLIDAY PAID"], 4),
            ("Plan", "HOLIDAY UNPAID"): round(plan_sub["HOLIDAY UNPAID"], 4),
            # % To be added to plan (R5:V5)
            ("% To be added to plan", "OUT OF OFFICE SHRINKAGE"): to_add_total,
            ("% To be added to plan", "PLANNED ABSENCE"): to_add_sub[
                "PLANNED ABSENCE"
            ],
            ("% To be added to plan", "ABSENCE"): to_add_sub["ABSENCE"],
            ("% To be added to plan", "HOLIDAY PAID"): to_add_sub[
                "HOLIDAY PAID"
            ],
            ("% To be added to plan", "HOLIDAY UNPAID"): to_add_sub[
                "HOLIDAY UNPAID"
            ],
            # Hours Reduction (W5:AA5)
            ("Hours reduction", "OUT OF OFFICE SHRINKAGE"): hours_red_total,
            ("Hours reduction", "PLANNED ABSENCE"): hours_red_sub[
                "PLANNED ABSENCE"
            ],
            ("Hours reduction", "ABSENCE"): hours_red_sub["ABSENCE"],
            ("Hours reduction", "HOLIDAY PAID"): hours_red_sub["HOLIDAY PAID"],
            ("Hours reduction", "HOLIDAY UNPAID"): hours_red_sub[
                "HOLIDAY UNPAID"
            ],
        }
        rows.append(row_dict)

    if as_dataframe:
        df = pd.DataFrame(rows)
        df.columns = pd.MultiIndex.from_tuples(df.columns)
        return df

    return rows



def generate_shrinkage_matrix_json(
    schedule_summary_payload: Union[str, Dict[str, Any]],
    assumptions_input: Optional[Dict[str, float]] = None,
    as_json_str: bool = True,
) -> Union[str, List[Dict[str, Any]]]:
    """Generates the wide WFM Shrinkage Planning Table formatted directly as JSON.

    Each date entry contains:
      - Date
      - Scheduled
      - Current (C5:G5)
      - Assumption (H5:L5)
      - Plan (M5:Q5)
      - % To be added to plan (R5:V5)
      - Hours reduction (W5:AA5)
    """
    if isinstance(schedule_summary_payload, str):
        try:
            data = json.loads(schedule_summary_payload)
        except Exception:
            data = {}
    else:
        data = schedule_summary_payload

    daily_totals_list = data.get("Daily Totals Summary", [])
    metrics_pct_list = data.get("Metrics as % of Scheduled Hours", [])

    base_sub_categories = [
        "PLANNED ABSENCE",
        "ABSENCE",
        "HOLIDAY PAID",
        "HOLIDAY UNPAID",
    ]

    # Default assumptions (as decimals: 20% = 0.20, 6% = 0.06)
    default_assumptions = {
        "PLANNED ABSENCE": 0.0,
        "ABSENCE": 0.20,
        "HOLIDAY PAID": 0.06,
        "HOLIDAY UNPAID": 0.0,
    }
    assumptions_config = {**default_assumptions, **(assumptions_input or {})}

    def _lookup(source: dict, key: str) -> float:
        norm = key.strip().lower()
        for k, v in source.items():
            if str(k).strip().lower() == norm:
                try:
                    return float(v) if v is not None else 0.0
                except (ValueError, TypeError):
                    return 0.0
        return 0.0

    output_records = []

    for dt, dp in zip(daily_totals_list, metrics_pct_list):
        date_str = dt.get("Date")
        scheduled_hours = _lookup(dt, "Scheduled")

        # -------------------------------------------------------------
        # 1. Current (C5:G5)
        # -------------------------------------------------------------
        current_sub = {cat: _lookup(dp, cat) for cat in base_sub_categories}
        current_total = _lookup(dp, "OUT OF OFFICE SHRINKAGE")
        if current_total == 0.0:
            current_total = sum(current_sub.values())

        current_dict = {
            "OUT OF OFFICE SHRINKAGE": round(current_total, 4),
            "PLANNED ABSENCE": round(current_sub["PLANNED ABSENCE"], 4),
            "ABSENCE": round(current_sub["ABSENCE"], 4),
            "HOLIDAY PAID": round(current_sub["HOLIDAY PAID"], 4),
            "HOLIDAY UNPAID": round(current_sub["HOLIDAY UNPAID"], 4),
        }

        # -------------------------------------------------------------
        # 2. Assumption (H5:L5)
        # -------------------------------------------------------------
        assumption_sub = {
            cat: assumptions_config.get(cat, 0.0) for cat in base_sub_categories
        }
        assumption_total = sum(assumption_sub.values())

        assumption_dict = {
            "OUT OF OFFICE SHRINKAGE": round(assumption_total, 4),
            "PLANNED ABSENCE": round(assumption_sub["PLANNED ABSENCE"], 4),
            "ABSENCE": round(assumption_sub["ABSENCE"], 4),
            "HOLIDAY PAID": round(assumption_sub["HOLIDAY PAID"], 4),
            "HOLIDAY UNPAID": round(assumption_sub["HOLIDAY UNPAID"], 4),
        }

        # -------------------------------------------------------------
        # 3. Plan (M5:Q5) -> =IF(Assumption > Current, Assumption, Current)
        # -------------------------------------------------------------
        plan_sub = {
            cat: max(assumption_sub[cat], current_sub[cat])
            for cat in base_sub_categories
        }
        plan_total = sum(plan_sub.values())  # =SUM(N5:Q5)

        plan_dict = {
            "OUT OF OFFICE SHRINKAGE": round(plan_total, 4),
            "PLANNED ABSENCE": round(plan_sub["PLANNED ABSENCE"], 4),
            "ABSENCE": round(plan_sub["ABSENCE"], 4),
            "HOLIDAY PAID": round(plan_sub["HOLIDAY PAID"], 4),
            "HOLIDAY UNPAID": round(plan_sub["HOLIDAY UNPAID"], 4),
        }

        # -------------------------------------------------------------
        # 4. % To be added to plan (R5:V5) -> =Plan - Current
        # -------------------------------------------------------------
        to_add_sub = {
            cat: round(plan_sub[cat] - current_sub[cat], 4)
            for cat in base_sub_categories
        }
        to_add_total = round(sum(to_add_sub.values()), 4)  # =SUM(S5:V5)

        to_add_dict = {
            "OUT OF OFFICE SHRINKAGE": to_add_total,
            "PLANNED ABSENCE": to_add_sub["PLANNED ABSENCE"],
            "ABSENCE": to_add_sub["ABSENCE"],
            "HOLIDAY PAID": to_add_sub["HOLIDAY PAID"],
            "HOLIDAY UNPAID": to_add_sub["HOLIDAY UNPAID"],
        }

        # -------------------------------------------------------------
        # 5. Hours reduction (W5:AA5) -> =(% To be added) * Scheduled ($C5)
        # -------------------------------------------------------------
        hours_red_sub = {
            cat: round(to_add_sub[cat] * scheduled_hours, 2)
            for cat in base_sub_categories
        }
        hours_red_total = round(sum(hours_red_sub.values()), 2)  # =SUM(X5:AA5)

        hours_red_dict = {
            "OUT OF OFFICE SHRINKAGE": hours_red_total,
            "PLANNED ABSENCE": hours_red_sub["PLANNED ABSENCE"],
            "ABSENCE": hours_red_sub["ABSENCE"],
            "HOLIDAY PAID": hours_red_sub["HOLIDAY PAID"],
            "HOLIDAY UNPAID": hours_red_sub["HOLIDAY UNPAID"],
        }

        # Assemble the date object
        output_records.append({
            "Date": date_str,
            "Scheduled": scheduled_hours,
            "Current": current_dict,
            "Assumption": assumption_dict,
            "Plan": plan_dict,
            "% To be added to plan": to_add_dict,
            "Hours reduction": hours_red_dict,
        })

    if as_json_str:
        return json.dumps(output_records, indent=4)
    return output_records