import json
from typing import Any, Dict, List, Union


def apply_daily_scaling_factor(
    schedule_data: Union[str, Dict[str, Any], List[Dict[str, Any]]],
    shrinkage_matrix: Union[str, List[Dict[str, Any]]],
    as_json_str: bool = True,
) -> Union[str, Dict[str, Any], List[Dict[str, Any]]]:
    """Applies the constant daily scaling factor and returns JSON:

    Daily Factor = 1 - (OUT_OF_OFFICE_SHRINKAGE_Hours_Reduction / Sum_of_all_7_activities)
    Slot Planned Value = Slot Raw Value * Daily Factor
    """
    # 1. Safely parse JSON strings to Python objects if needed
    if isinstance(schedule_data, str):
        try:
            schedule_data = json.loads(schedule_data)
        except Exception:
            pass

    if isinstance(shrinkage_matrix, str):
        try:
            shrinkage_matrix = json.loads(shrinkage_matrix)
        except Exception:
            shrinkage_matrix = []

    if not isinstance(shrinkage_matrix, list):
        shrinkage_matrix = [shrinkage_matrix] if shrinkage_matrix else []

    # 2. Map each Date to its OUT OF OFFICE SHRINKAGE Hours Reduction (Assumptions!$W5)
    ooo_hours_reduction_by_date = {}
    for entry in shrinkage_matrix:
        if not isinstance(entry, dict):
            continue

        d_str = entry.get("Date") or entry.get("date")
        reduction_dict = entry.get("Hours reduction") or entry.get(
            "hours_reduction", {}
        )

        val = 0.0
        if isinstance(reduction_dict, dict):
            for k, v in reduction_dict.items():
                if "out of office shrinkage" in str(k).strip().lower():
                    try:
                        val = float(v or 0.0)
                    except (ValueError, TypeError):
                        val = 0.0
                    break
        ooo_hours_reduction_by_date[d_str] = val

    # The 7 productive categories
    productive_keys = [
        "Available",
        "Back Office",
        "Chat",
        "Email",
        "Multimedia",
        "Outbound",
        "Overtime",
    ]

    # Normalize day entries list
    if isinstance(schedule_data, dict):
        day_entries = schedule_data.get("daily_data", [schedule_data])
    elif isinstance(schedule_data, list):
        day_entries = schedule_data
    else:
        day_entries = []

    for day_obj in day_entries:
        if not isinstance(day_obj, dict):
            continue

        curr_date = day_obj.get("date") or day_obj.get("Date")
        slots = day_obj.get("slots", [])

        # Step A: Denominator = Sum of all 7 productive activities on that day (in staff hours)
        total_sum_7_activities = 0.0
        for slot in slots:
            for act in productive_keys:
                try:
                    total_sum_7_activities += float(slot.get(act, 0.0) or 0.0)
                except (ValueError, TypeError):
                    pass

        # 30-min FTEs sum divided by 2 to convert to staff hours
        daily_productive_hours = total_sum_7_activities / 2.0

        # Step B: Numerator = OUT OF OFFICE SHRINKAGE on that day
        ooo_hours_red = ooo_hours_reduction_by_date.get(curr_date, 0.0)

        # Step C: The constant daily factor
        if daily_productive_hours > 0:
            daily_factor = 1.0 - (ooo_hours_red / daily_productive_hours)
        else:
            daily_factor = 1.0

        day_obj["daily_scaling_factor"] = round(daily_factor, 6)

        # Step D: Multiply raw slot values by the daily factor
        for slot in slots:
            for act in productive_keys:
                try:
                    raw_val = float(slot.get(act, 0.0) or 0.0)
                except (ValueError, TypeError):
                    raw_val = 0.0
                slot[f"Planned {act}"] = round(raw_val * daily_factor, 4)

    # Return as formatted JSON string by default
    if as_json_str:
        return json.dumps(schedule_data, indent=4)
    return schedule_data