# import json
# from typing import Any, Dict, List, Union


# def format_absence_holiday_json(
#     input_json: Union[str, Dict[str, Any]],
#     interval_mins: int = 30,
#     as_json_str: bool = True,
# ) -> Union[str, Dict[str, Any]]:
#     """Parses schedule slot JSON, extracts target categories, and divides each

#     value (and total) by interval_mins. If a category is missing or 0, it
#     evaluates to 0.0.
#     """
#     if isinstance(input_json, str):
#         data = json.loads(input_json)
#     else:
#         data = input_json

#     def _get_category_value(categories_dict: dict, target_key: str) -> float:
#         """Safely retrieves float value with case-insensitive key lookup; defaults to 0.0."""
#         if not categories_dict or not isinstance(categories_dict, dict):
#             return 0.0
#         for key, val in categories_dict.items():
#             if str(key).strip().lower() == target_key.lower():
#                 try:
#                     if val is None:
#                         return 0.0
#                     return float(val)
#                 except (ValueError, TypeError):
#                     return 0.0
#         return 0.0

#     def _divide_safe(val: float, divisor: float) -> float:
#         """Divides val by divisor; returns 0.0 if value is 0 or divisor is invalid."""
#         if not val or divisor <= 0:
#             return 0.0
#         return round(val / divisor, 4)

#     # 1. Normalize input to handle both multi-day ('daily_data') and single-day payloads
#     if "daily_data" in data and isinstance(data["daily_data"], list):
#         day_entries = data["daily_data"]
#     else:
#         day_entries = [
#             {"date": data.get("date"), "slots": data.get("slots", [])}
#         ]

#     # 2. Process all slots across all dates
#     all_transformed_slots: List[Dict[str, Any]] = []

#     for day in day_entries:
#         curr_date = day.get("date")
#         slots = day.get("slots", [])

#         for slot in slots:
#             slot_time = slot.get("slot_time")
#             start_time = slot.get("start_time")
#             end_time = slot.get("end_time")
#             prim_cats = slot.get("primary_categories", {})

#             # Extract raw values (defaults to 0.0 if not found)
#             raw_planned_absence = _get_category_value(
#                 prim_cats, "Planned Absence"
#             )
#             raw_absence = _get_category_value(prim_cats, "Absence")
#             raw_holiday_paid = _get_category_value(prim_cats, "Holiday Paid")
#             raw_holiday_unpaid = _get_category_value(
#                 prim_cats, "Holiday Unpaid"
#             )

#             # Divide each metric by interval_mins
#             planned_absence = _divide_safe(raw_planned_absence, interval_mins)
#             absence = _divide_safe(raw_absence, interval_mins)
#             holiday_paid = _divide_safe(raw_holiday_paid, interval_mins)
#             holiday_unpaid = _divide_safe(raw_holiday_unpaid, interval_mins)

#             # Total is the sum of the normalized values
#             total_val = round(
#                 planned_absence + absence + holiday_paid + holiday_unpaid, 4
#             )

#             all_transformed_slots.append({
#                 "date": curr_date,
#                 "interval": interval_mins,
#                 "slot_time": slot_time,
#                 "start_time": start_time,
#                 "end_time": end_time,
#                 "Planned Absence": planned_absence,
#                 "Absence": absence,
#                 "Holiday Paid": holiday_paid,
#                 "Holiday Unpaid": holiday_unpaid,
#                 "total": total_val,
#             })

#     result = {
#         "start_date": data.get("start_date", data.get("date")),
#         "end_date": data.get("end_date", data.get("date")),
#         "interval": interval_mins,
#         "categories": [
#             "Planned Absence",
#             "Absence",
#             "Holiday Paid",
#             "Holiday Unpaid",
#         ],
#         "slots": all_transformed_slots,
#     }

#     if as_json_str:
#         return json.dumps(result, indent=4)
#     return result


import json
from typing import Any, Dict, List, Union


def format_comprehensive_schedule_metrics(
    input_json: Union[str, Dict[str, Any]],
    interval_mins: int = 30,
    as_json_str: bool = True,
) -> Union[str, Dict[str, Any]]:
    """Calculates all interval-based and daily total metrics from schedule slot JSON.

    Combines Primary Category metrics with Grouping metrics and evaluates:
      - OUT OF OFFICE SHRINKAGE
      - IN OFFICE SHRINKAGE
      - SCHEDULED AVAILABLE
      - SCHEDULED
      - IN OFFICE
    """
    if isinstance(input_json, str):
        data = json.loads(input_json)
    else:
        data = input_json

    def _get_val(source_dict: dict, target_key: str) -> float:
        """Safely fetch numeric value with case-insensitive and stripped lookup."""
        if not source_dict or not isinstance(source_dict, dict):
            return 0.0
        target_norm = target_key.strip().lower()
        for k, v in source_dict.items():
            if str(k).strip().lower() == target_norm:
                try:
                    return float(v) if v is not None else 0.0
                except (ValueError, TypeError):
                    return 0.0
        return 0.0

    def _div(val: float) -> float:
        """Divide by interval_mins; safely returns 0.0 if zero or invalid interval."""
        if not val or interval_mins <= 0:
            return 0.0
        return round(val / interval_mins, 4)

    # 1. Normalize input for multi-day ('daily_data') or single-day payloads
    if "daily_data" in data and isinstance(data["daily_data"], list):
        day_entries = data["daily_data"]
    else:
        day_entries = [
            {"date": data.get("date"), "slots": data.get("slots", [])}
        ]

    daily_results = []

    for day in day_entries:
        curr_date = day.get("date")
        slots = day.get("slots", [])

        slot_records = []

        # Keys to accumulate daily sums
        all_metric_keys = [
            # Primary Categories (Out of Office)
            "Planned Absence",
            "Absence",
            "Holiday Paid",
            "Holiday Unpaid",
            # Grouping Categories
            "Breaks",
            "Investment",
            "Training",
            "Other Jobs",
            "System Downtime",
            "Client Downtime",
            "Available",
            "Back Office",
            "Chat",
            "Email",
            "Multimedia",
            "Outbound",
            "Overtime",
            # Calculated Aggregates
            "Out of Office Shrinkage",
            "In Office Shrinkage",
            "Scheduled Available",
            "Scheduled",
            "In Office",
        ]

        # Initialize daily totals accumulator
        daily_totals = {k: 0.0 for k in all_metric_keys}

        for slot in slots:
            slot_time = slot.get("slot_time")
            start_time = slot.get("start_time")
            end_time = slot.get("end_time")

            prim_cats = slot.get("primary_categories", {})
            groupings = slot.get("groupings", {})

            # -------------------------------------------------------------
            # A. Extract Primary Category (Out of Office) - divided by interval
            # -------------------------------------------------------------
            planned_abs = _div(_get_val(prim_cats, "Planned Absence"))
            absence = _div(_get_val(prim_cats, "Absence"))
            hol_paid = _div(_get_val(prim_cats, "Holiday Paid"))
            hol_unpaid = _div(_get_val(prim_cats, "Holiday Unpaid"))

            # -------------------------------------------------------------
            # B. Extract Groupings - divided by interval
            # -------------------------------------------------------------
            breaks = _div(_get_val(groupings, "Breaks"))
            investment = _div(_get_val(groupings, "Investment"))
            training = _div(_get_val(groupings, "Training"))
            other_jobs = _div(_get_val(groupings, "Other Jobs"))
            sys_downtime = _div(_get_val(groupings, "System Downtime"))
            client_downtime = _div(_get_val(groupings, "Client Downtime"))
            available = _div(_get_val(groupings, "Available"))
            back_office = _div(_get_val(groupings, "Back Office"))
            chat = _div(_get_val(groupings, "Chat"))
            email = _div(_get_val(groupings, "Email"))
            multimedia = _div(_get_val(groupings, "Multimedia"))
            outbound = _div(_get_val(groupings, "Outbound"))
            overtime = _div(_get_val(groupings, "Overtime"))

            # -------------------------------------------------------------
            # C. Formula Calculations
            # -------------------------------------------------------------
            # OUT OF OFFICE SHRINKAGE = PLANNED ABSENCE + ABSENCE + HOLIDAY PAID + HOLIDAY UNPAID
            ooo_shrinkage = round(
                planned_abs + absence + hol_paid + hol_unpaid, 4
            )

            # IN OFFICE SHRINKAGE = BREAKS + INVESTMENT + TRAINING + OTHER JOBS + CLIENT DOWNTIME
            in_office_shrinkage = round(
                breaks + investment + training + other_jobs + client_downtime, 4
            )

            # SCHEDULED AVAILABLE = AVAILABLE + BACK OFFICE + CHAT + EMAIL + MULTIMEDIA + OUTBOUND + OVERTIME
            sched_available = round(
                available
                + back_office
                + chat
                + email
                + multimedia
                + outbound
                + overtime,
                4,
            )

            # SCHEDULED = OUT OF OFFICE SHRINKAGE + IN OFFICE SHRINKAGE + SCHEDULED AVAILABLE
            scheduled = round(
                ooo_shrinkage + in_office_shrinkage + sched_available, 4
            )

            # IN OFFICE = SCHEDULED - OUT OF OFFICE SHRINKAGE
            in_office = round(scheduled - ooo_shrinkage, 4)

            slot_dict = {
                "date": curr_date,
                "interval": interval_mins,
                "slot_time": slot_time,
                "start_time": start_time,
                "end_time": end_time,
                # Primary Categories
                "Planned Absence": planned_abs,
                "Absence": absence,
                "Holiday Paid": hol_paid,
                "Holiday Unpaid": hol_unpaid,
                # Groupings
                "Breaks": breaks,
                "Investment": investment,
                "Training": training,
                "Other Jobs": other_jobs,
                "System Downtime": sys_downtime,
                "Client Downtime": client_downtime,
                "Available": available,
                "Back Office": back_office,
                "Chat": chat,
                "Email": email,
                "Multimedia": multimedia,
                "Outbound": outbound,
                "Overtime": overtime,
                # Calculations
                "Out of Office Shrinkage": ooo_shrinkage,
                "In Office Shrinkage": in_office_shrinkage,
                "Scheduled Available": sched_available,
                "Scheduled": scheduled,
                "In Office": in_office,
            }

            slot_records.append(slot_dict)

            # Accumulate into daily totals
            for k in all_metric_keys:
                daily_totals[k] = round(daily_totals[k] + slot_dict[k], 4)

        daily_results.append({
            "date": curr_date,
            "daily_totals": daily_totals,
            "slots": slot_records,
        })

    result = {
        "start_date": data.get("start_date", data.get("date")),
        "end_date": data.get("end_date", data.get("date")),
        "interval": interval_mins,
        "daily_data": daily_results,
    }

    if as_json_str:
        return json.dumps(result, indent=4)
    return result