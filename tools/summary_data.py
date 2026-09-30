import json
from typing import Any, Dict, List, Union


def extract_schedule_daily_totals(
    data: Union[str, Dict[str, Any], List[Dict[str, Any]]],
    as_json_str: bool = True,
) -> Union[str, Dict[str, Any]]:
    """Groups all dates under two primary top-level keys:
      - 'Daily Totals Summary': List of raw totals per date (divided by 2 for staff hours)
      - 'Metrics as % of Scheduled Hours': List of decimal ratios per date (e.g. 0.80 for 80%)
    """
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            return "{}" if as_json_str else {}

    # Extract the entries list
    if isinstance(data, dict):
        day_entries = data.get("daily_data", [])
    elif isinstance(data, list):
        day_entries = data
    else:
        day_entries = []

    daily_totals_summary_list = []
    metrics_pct_summary_list = []

    for entry in day_entries:
        if not isinstance(entry, dict):
            continue

        date_str = entry.get("date") or entry.get("Date")
        raw_totals = entry.get("daily_totals") or entry.get("Daily Totals Summary") or {}

        # 1. Divide all numeric metric totals by 2
        halved_totals = {}
        for metric, val in raw_totals.items():
            try:
                num_val = float(val) if val is not None else 0.0
            except (ValueError, TypeError):
                num_val = 0.0
            halved_totals[metric] = round(num_val / 2.0, 4)

        # 2. Extract halved Scheduled value for ratio calculations
        scheduled_val = 0.0
        for k, v in halved_totals.items():
            if str(k).strip().lower() == "scheduled":
                scheduled_val = float(v)
                break

        # 3. Calculate decimal ratios (e.g., 0.80 for 80%)
        fraction_of_scheduled = {}
        for metric, val in halved_totals.items():
            num_val = float(val)
            if scheduled_val > 0:
                fraction_val = round(num_val / scheduled_val, 4)
            else:
                fraction_val = 0.0
            fraction_of_scheduled[metric] = fraction_val

        # 4. Append to respective top-level lists
        daily_totals_summary_list.append({
            "Date": date_str,
            **halved_totals
        })

        metrics_pct_summary_list.append({
            "Date": date_str,
            **fraction_of_scheduled
        })

    result_payload = {
        "Daily Totals Summary": daily_totals_summary_list,
        "Metrics as % of Scheduled Hours": metrics_pct_summary_list,
    }

    if as_json_str:
        return json.dumps(result_payload, indent=4)
    return result_payload