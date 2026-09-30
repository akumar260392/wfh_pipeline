# import json
# from typing import Any, Dict, List, Union
# import pandas as pd


# def generate_supply_vs_demand_table(
#     forecast_data: Union[str, Dict[str, Any], List[Dict[str, Any]]],
#     schedule_with_planned: Union[str, Dict[str, Any], List[Dict[str, Any]]],
#     as_json_str: bool = True,
#     as_dataframe: bool = False,
# ) -> Union[str, pd.DataFrame, List[Dict[str, Any]]]:
#     """Generates the Supply vs Demand table.

#     Both slot-level and date-level totals use the exact same formula sequence:
#       1. Supply = Planned Available + Planned Overtime
#       2. Supply vs Demand = Supply - Required FTE
#       3. Forecast Occupancy = min(1.0, Workload / Supply)
#     """
#     # 1. Safely parse JSON strings
#     if isinstance(forecast_data, str):
#         try:
#             forecast_data = json.loads(forecast_data)
#         except Exception:
#             forecast_data = []

#     if isinstance(schedule_with_planned, str):
#         try:
#             schedule_with_planned = json.loads(schedule_with_planned)
#         except Exception:
#             schedule_with_planned = []

#     # 2. Normalize inputs (handles list or dict without calling .get() on list)
#     if isinstance(forecast_data, list):
#         f_days = forecast_data
#     elif isinstance(forecast_data, dict):
#         f_days = (
#             forecast_data.get("daily_data")
#             or forecast_data.get("data")
#             or [forecast_data]
#         )
#     else:
#         f_days = []

#     if isinstance(schedule_with_planned, list):
#         s_days = schedule_with_planned
#     elif isinstance(schedule_with_planned, dict):
#         s_days = (
#             schedule_with_planned.get("daily_data")
#             or schedule_with_planned.get("data")
#             or [schedule_with_planned]
#         )
#     else:
#         s_days = []

#     def _norm_time(t_val: Any) -> str:
#         if not t_val:
#             return ""
#         parts = str(t_val).strip().split(":")
#         if len(parts) >= 2:
#             return f"{int(parts[0]):02d}:{int(parts[1]):02d}"
#         return str(t_val).strip()

#     def _get_val(source: dict, candidate_keys: List[str]) -> float:
#         for target in candidate_keys:
#             target_norm = target.strip().lower()
#             for k, v in source.items():
#                 if str(k).strip().lower() == target_norm:
#                     try:
#                         return float(v) if v is not None else 0.0
#                     except (ValueError, TypeError):
#                         pass
#         return 0.0

#     # 3. Build Schedule index: (Date, Start_Time) -> slot
#     schedule_lookup = {}
#     for day in s_days:
#         if not isinstance(day, dict):
#             continue
#         d_str = str(day.get("date") or day.get("Date") or "").strip()[:10]
#         for slot in day.get("slots", []):
#             start_t = (
#                 slot.get("start_time")
#                 or slot.get("Start Slot Time")
#                 or slot.get("Start Time")
#             )
#             if not start_t and "slot_time" in slot:
#                 start_t = str(slot["slot_time"]).split("-")[0].strip()
#             norm_start = _norm_time(start_t)
#             if d_str and norm_start:
#                 schedule_lookup[(d_str, norm_start)] = slot

#     daily_results = []
#     flat_rows_for_df = []

#     # 4. Iterate over Forecast Days
#     for day in f_days:
#         if not isinstance(day, dict):
#             continue
#         d_str = str(day.get("date") or day.get("Date") or "").strip()[:10]
#         f_slots = day.get("slots", [])

#         # Accumulators for Day-Level sums
#         total_offered = 0.0
#         total_call_seconds = 0.0
#         raw_sum_req_fte = 0.0
#         raw_sum_planned_avail = 0.0
#         raw_sum_planned_ot = 0.0

#         slots_output = []

#         for f_slot in f_slots:
#             start_t = (
#                 f_slot.get("Start Slot Time")
#                 or f_slot.get("start_time")
#                 or f_slot.get("Start Time")
#             )
#             end_t = (
#                 f_slot.get("End Slot Time")
#                 or f_slot.get("end_time")
#                 or f_slot.get("End Time")
#             )
#             slot_label = f_slot.get("Slot Time") or f_slot.get("slot_time")

#             if not start_t and slot_label and "-" in slot_label:
#                 parts = slot_label.split("-")
#                 start_t, end_t = parts[0].strip(), parts[1].strip()

#             norm_start = _norm_time(start_t)
#             norm_end = _norm_time(end_t)
#             if not slot_label:
#                 slot_label = f"{norm_start}-{norm_end}"

#             s_slot = schedule_lookup.get((d_str, norm_start), {})

#             offered = _get_val(
#                 f_slot, ["OFFERED (Calls)", "Offered", "Calls", "OFFERED"]
#             )
#             aht = _get_val(
#                 f_slot, ["AHT (Seconds)", "AHT", "Average Handle Time"]
#             )
#             req_fte = _get_val(
#                 f_slot,
#                 [
#                     "Calculated Required FTE",
#                     "DB Required FTE",
#                     "Required FTE",
#                     "DB Revised FTE",
#                 ],
#             )

#             planned_avail = _get_val(
#                 s_slot, ["Planned Available", "planned_available", "Available"]
#             )
#             planned_ot = _get_val(
#                 s_slot, ["Planned Overtime", "planned_overtime", "Overtime"]
#             )

#             # Slot Calculations
#             workload_erlangs = (offered * aht) / 1800.0
#             supply_headcount = round(planned_avail + planned_ot, 4)
#             supply_vs_demand = round(supply_headcount - req_fte, 4)

#             if supply_headcount > 0:
#                 raw_occ = workload_erlangs / supply_headcount
#                 forecast_occ = round(min(1.0, raw_occ), 4)
#                 forecast_occ_str = f"{forecast_occ * 100:.1f}%"
#             else:
#                 forecast_occ = 0.0
#                 forecast_occ_str = "-"

#             # Accumulate interval totals
#             total_offered += offered
#             total_call_seconds += offered * aht
#             raw_sum_req_fte += req_fte
#             raw_sum_planned_avail += planned_avail
#             raw_sum_planned_ot += planned_ot

#             slot_record = {
#                 "Date": d_str,
#                 "Slot Time": slot_label,
#                 "Start Time": norm_start,
#                 "End Time": norm_end,
#                 "Offered": round(offered, 2),
#                 "AHT": round(aht, 2),
#                 "Workload (Erlangs)": round(workload_erlangs, 4),
#                 "REQUIRED FTE": round(req_fte, 4),
#                 "PLANNED AVAILABLE": round(planned_avail, 4),
#                 "PLANNED OVERTIME": round(planned_ot, 4),
#                 "PLANNED AVAILABLE + OVERTIME": supply_headcount,
#                 "SUPPLY VS DEMAND": supply_vs_demand,
#                 "FORECAST OCCUPANCY": forecast_occ,
#                 "FORECAST OCCUPANCY (%)": forecast_occ_str,
#             }
#             slots_output.append(slot_record)
#             flat_rows_for_df.append(slot_record)

#         # ------------------------------------------------------------------
#         # DATE TOTALS: Same approach as 30-min calculations (in Staff-Hours)
#         # ------------------------------------------------------------------
#         # 1. Total Required FTE (Slot FTEs sum divided by 2)
#         total_req_fte = round(raw_sum_req_fte / 2.0, 4)

#         # 2. Total Planned Available and Total Planned Overtime (divided by 2)
#         total_planned_avail = round(raw_sum_planned_avail / 2.0, 4)
#         total_planned_ot = round(raw_sum_planned_ot / 2.0, 4)

#         # 3. Total Supply = Total Planned Available + Total Planned Overtime
#         total_supply = round(total_planned_avail + total_planned_ot, 4)

#         # 4. Total Supply vs Demand = Supply - Required FTE
#         total_supply_vs_demand = round(total_supply - total_req_fte, 4)

#         # 5. Total Workload & Occupancy
#         total_workload_hours = round(total_call_seconds / 3600.0, 4)
#         weighted_aht = (
#             round(total_call_seconds / total_offered, 2)
#             if total_offered > 0
#             else 0.0
#         )

#         if total_supply > 0:
#             daily_occ = round(min(1.0, total_workload_hours / total_supply), 4)
#             daily_occ_str = f"{daily_occ * 100:.1f}%"
#         else:
#             daily_occ = 0.0
#             daily_occ_str = "-"

#         # Mirrors the slot keys directly
#         daily_summary = {
#             "Date": d_str,
#             "OFFERED": round(total_offered, 2),
#             "AHT": weighted_aht,
#             "Workload (Staff Hours)": total_workload_hours,
#             "REQUIRED FTE": total_req_fte,
#             "PLANNED AVAILABLE": total_planned_avail,
#             "PLANNED OVERTIME": total_planned_ot,
#             "PLANNED AVAILABLE + OVERTIME": total_supply,
#             "SUPPLY VS DEMAND": total_supply_vs_demand,
#             "FORECAST OCCUPANCY": daily_occ,
#             "FORECAST OCCUPANCY (%)": daily_occ_str,
#         }

#         daily_results.append({
#             "Date": d_str,
#             "daily_totals": daily_summary,
#             "slots": slots_output,
#         })

#     if as_dataframe:
#         return pd.DataFrame(flat_rows_for_df)
#     if as_json_str:
#         return json.dumps(daily_results, indent=4)
#     return daily_results


import json
import math
from typing import Any, Dict, List, Union
import pandas as pd

def calculate_erlang_c_service_level(
    agents: float,
    threshold_seconds: float,
    offered_calls: float,
    aht_seconds: float,
    interval_seconds: float = 1800.0
) -> float:
    """
    Exact replica of Excel add-in:
      =SLA(PLANNED_SUPPLY, THRESHOLD, OFFERED, AHT)
    """
    if offered_calls <= 0.0:
        return 1.0  # 100% SLA if no calls
    if agents <= 0.0:
        return 0.0  # 0% SLA if no staff
    if aht_seconds <= 0.0:
        return 1.0

    if threshold_seconds <= 0.0:
        threshold_seconds = 20.0

    # Traffic intensity (Erlangs)
    arrival_rate = offered_calls / interval_seconds
    erlangs = arrival_rate * aht_seconds

    # Discrete agent count: Excel Erlang add-ins evaluate on discrete integer servers
    # If fractional, Excel uses ceiling (e.g. 0.88 FTE = 1 active staff)
    n_servers = max(1, int(math.ceil(round(agents, 4))))

    # If workload >= agents, queue overflows -> 0% SLA
    if n_servers <= erlangs:
        return 0.0

    # Stable Erlang-B to Erlang-C calculation
    inv_b = 1.0
    for i in range(1, n_servers + 1):
        inv_b = 1.0 + (inv_b * (i / erlangs))
    b = 1.0 / inv_b

    rho = erlangs / n_servers
    if rho >= 1.0:
        return 0.0

    denom = 1.0 - rho + (rho * b)
    if denom <= 0:
        return 0.0

    pw = b / denom
    pw = max(0.0, min(1.0, pw))

    # SL = 1 - Pw * exp(-(N - A) * (t / AHT))
    decay = math.exp(-(n_servers - erlangs) * (threshold_seconds / aht_seconds))
    sla = max(0.0, min(1.0, 1.0 - (pw * decay)))
    
    return round(float(sla), 4)

def generate_supply_vs_demand_table(
    forecast_data: Union[str, Dict[str, Any], List[Dict[str, Any]]],
    schedule_with_planned: Union[str, Dict[str, Any], List[Dict[str, Any]]],
    as_json_str: bool = True,
    as_dataframe: bool = False,
) -> Union[str, pd.DataFrame, List[Dict[str, Any]]]:
    """Generates Supply vs Demand table including FORECAST SERVICE LEVEL.
    Computes both 30-minute interval metrics and date-level rollups.
    """
    # 1. Safely parse JSON strings
    if isinstance(forecast_data, str):
        try:
            forecast_data = json.loads(forecast_data)
        except Exception:
            forecast_data = []

    if isinstance(schedule_with_planned, str):
        try:
            schedule_with_planned = json.loads(schedule_with_planned)
        except Exception:
            schedule_with_planned = []

    # 2. Normalize inputs (handles list or dict)
    if isinstance(forecast_data, list):
        f_days = forecast_data
    elif isinstance(forecast_data, dict):
        f_days = (
            forecast_data.get("daily_data")
            or forecast_data.get("data")
            or [forecast_data]
        )
    else:
        f_days = []

    if isinstance(schedule_with_planned, list):
        s_days = schedule_with_planned
    elif isinstance(schedule_with_planned, dict):
        s_days = (
            schedule_with_planned.get("daily_data")
            or schedule_with_planned.get("data")
            or [schedule_with_planned]
        )
    else:
        s_days = []

    def _norm_time(t_val: Any) -> str:
        if not t_val:
            return ""
        parts = str(t_val).strip().split(":")
        if len(parts) >= 2:
            return f"{int(parts[0]):02d}:{int(parts[1]):02d}"
        return str(t_val).strip()

    def _get_val(source: dict, candidate_keys: List[str]) -> float:
        for target in candidate_keys:
            target_norm = target.strip().lower()
            for k, v in source.items():
                if str(k).strip().lower() == target_norm:
                    try:
                        return float(v) if v is not None else 0.0
                    except (ValueError, TypeError):
                        pass
        return 0.0

    # 3. Build Schedule index: (Date, Start_Time) -> slot
    schedule_lookup = {}
    for day in s_days:
        if not isinstance(day, dict):
            continue
        d_str = str(day.get("date") or day.get("Date") or "").strip()[:10]
        for slot in day.get("slots", []):
            start_t = (
                slot.get("start_time")
                or slot.get("Start Slot Time")
                or slot.get("Start Time")
            )
            if not start_t and "slot_time" in slot:
                start_t = str(slot["slot_time"]).split("-")[0].strip()
            norm_start = _norm_time(start_t)
            if d_str and norm_start:
                schedule_lookup[(d_str, norm_start)] = slot

    daily_results = []
    flat_rows_for_df = []

    # 4. Iterate over Forecast Days
    for day in f_days:
        if not isinstance(day, dict):
            continue
        d_str = str(day.get("date") or day.get("Date") or "").strip()[:10]
        f_slots = day.get("slots", [])

        # Default day threshold (Demand!C26)
        day_total_dict = day.get("total", {})
        default_threshold = _get_val(
            day_total_dict,
            [
                "Service Level Threshold Seconds",
                "SL Threshold Seconds",
                "Threshold Seconds",
                "Threshold",
                "threshold",
            ],
        )
        if default_threshold <= 0.0:
            default_threshold = 20.0

        total_offered = 0.0
        total_call_seconds = 0.0
        raw_sum_req_fte = 0.0
        raw_sum_planned_avail = 0.0
        raw_sum_planned_ot = 0.0
        total_sla_calls_handled_in_threshold = 0.0

        slots_output = []

        for f_slot in f_slots:
            start_t = (
                f_slot.get("Start Slot Time")
                or f_slot.get("start_time")
                or f_slot.get("Start Time")
            )
            end_t = (
                f_slot.get("End Slot Time")
                or f_slot.get("end_time")
                or f_slot.get("End Time")
            )
            slot_label = f_slot.get("Slot Time") or f_slot.get("slot_time")

            if not start_t and slot_label and "-" in slot_label:
                parts = slot_label.split("-")
                start_t, end_t = parts[0].strip(), parts[1].strip()

            norm_start = _norm_time(start_t)
            norm_end = _norm_time(end_t)
            if not slot_label:
                slot_label = f"{norm_start}-{norm_end}"

            s_slot = schedule_lookup.get((d_str, norm_start), {})

            # Metric extraction
            offered = _get_val(
                f_slot, ["OFFERED (Calls)", "Offered", "Calls", "OFFERED"]
            )
            aht = _get_val(
                f_slot, ["AHT (Seconds)", "AHT", "Average Handle Time"]
            )
            req_fte = _get_val(
                f_slot,
                [
                    "Calculated Required FTE",
                    "DB Required FTE",
                    "Required FTE",
                    "DB Revised FTE",
                ],
            )
            threshold = _get_val(
                f_slot,
                [
                    "Service Level Threshold Seconds",
                    "Threshold Seconds",
                    "Threshold",
                ],
            )
            if threshold <= 0.0:
                threshold = default_threshold

            planned_avail = _get_val(
                s_slot, ["Planned Available", "planned_available", "Available"]
            )
            planned_ot = _get_val(
                s_slot, ["Planned Overtime", "planned_overtime", "Overtime"]
            )

            # Core Calculations
            workload_erlangs = (offered * aht) / 1800.0
            supply_headcount = round(planned_avail + planned_ot, 4)
            supply_vs_demand = round(supply_headcount - req_fte, 4)

            # Occupancy
            if supply_headcount > 0:
                raw_occ = workload_erlangs / supply_headcount
                forecast_occ = round(min(1.0, raw_occ), 4)
                forecast_occ_str = f"{forecast_occ * 100:.1f}%"
            else:
                forecast_occ = 0.0
                forecast_occ_str = "-"

            # Forecast Service Level using updated Erlang-C formula
            slot_sla = calculate_erlang_c_service_level(
                agents=supply_headcount,
                threshold_seconds=threshold,
                offered_calls=offered,
                aht_seconds=aht,
                interval_seconds=1800.0,
            )
            slot_sla_str = f"{slot_sla * 100:.1f}%" if offered > 0 else "-"

            # Accumulations
            total_offered += offered
            total_call_seconds += offered * aht
            raw_sum_req_fte += req_fte
            raw_sum_planned_avail += planned_avail
            raw_sum_planned_ot += planned_ot
            total_sla_calls_handled_in_threshold += slot_sla * offered

            slot_record = {
                "Date": d_str,
                "Slot Time": slot_label,
                "Start Time": norm_start,
                "End Time": norm_end,
                "Offered": round(offered, 2),
                "AHT": round(aht, 2),
                "Workload (Erlangs)": round(workload_erlangs, 4),
                "REQUIRED FTE": round(req_fte, 4),
                "PLANNED AVAILABLE": round(planned_avail, 4),
                "PLANNED OVERTIME": round(planned_ot, 4),
                "PLANNED AVAILABLE + OVERTIME": supply_headcount,
                "SUPPLY VS DEMAND": supply_vs_demand,
                "FORECAST OCCUPANCY": forecast_occ,
                "FORECAST OCCUPANCY (%)": forecast_occ_str,
                "FORECAST SERVICE LEVEL": slot_sla,
                "FORECAST SERVICE LEVEL (%)": slot_sla_str,
            }
            slots_output.append(slot_record)
            flat_rows_for_df.append(slot_record)

        # -------------------------------------------------------------
        # Date-Level Rollups (Matching 30-min logic in Staff-Hours)
        # -------------------------------------------------------------
        total_req_fte = round(raw_sum_req_fte / 2.0, 4)
        total_planned_avail = round(raw_sum_planned_avail / 2.0, 4)
        total_planned_ot = round(raw_sum_planned_ot / 2.0, 4)
        total_supply = round(total_planned_avail + total_planned_ot, 4)
        total_supply_vs_demand = round(total_supply - total_req_fte, 4)

        total_workload_hours = round(total_call_seconds / 3600.0, 4)
        weighted_aht = (
            round(total_call_seconds / total_offered, 2)
            if total_offered > 0
            else 0.0
        )

        if total_supply > 0:
            daily_occ = round(min(1.0, total_workload_hours / total_supply), 4)
            daily_occ_str = f"{daily_occ * 100:.1f}%"
        else:
            daily_occ = 0.0
            daily_occ_str = "-"

        # Daily SLA: Volume-weighted SLA of all intervals
        if total_offered > 0:
            daily_sla = round(
                total_sla_calls_handled_in_threshold / total_offered, 4
            )
            daily_sla_str = f"{daily_sla * 100:.1f}%"
        else:
            daily_sla = 1.0
            daily_sla_str = "100.0%"

        daily_summary = {
            "Date": d_str,
            "OFFERED": round(total_offered, 2),
            "AHT": weighted_aht,
            "Workload (Staff Hours)": total_workload_hours,
            "REQUIRED FTE": total_req_fte,
            "PLANNED AVAILABLE": total_planned_avail,
            "PLANNED OVERTIME": total_planned_ot,
            "PLANNED AVAILABLE + OVERTIME": total_supply,
            "SUPPLY VS DEMAND": total_supply_vs_demand,
            "FORECAST OCCUPANCY": daily_occ,
            "FORECAST OCCUPANCY (%)": daily_occ_str,
            "FORECAST SERVICE LEVEL": daily_sla,
            "FORECAST SERVICE LEVEL (%)": daily_sla_str,
        }

        daily_results.append({
            "Date": d_str,
            "daily_totals": daily_summary,
            "slots": slots_output,
        })

    if as_dataframe:
        return pd.DataFrame(flat_rows_for_df)
    if as_json_str:
        return json.dumps(daily_results, indent=4)
    return daily_results