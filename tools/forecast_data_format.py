import json
import math
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Union

import pandas as pd
from sqlalchemy import text

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from db.db_init import SessionLocal


# ==============================================================================
# 1. ERLANG C / FRACTIONAL AGENTS FORMULAS
# ==============================================================================
def enrlang_b(agents: float, traffic: float) -> float:
    if agents < 0:
        return 1.0
    b = 1.0
    for n in range(1, int(agents) + 1):
        b = (traffic * b) / (n + traffic * b)
    return b


def enlang_c(agents: float, traffic: float) -> float:
    if agents <= 0 or traffic >= agents:
        return 1.0
    b = enrlang_b(agents, traffic)
    rho = traffic / agents
    return b / (rho * b + (1.0 - rho))


def service_level(agents: float, traffic: float, aht: float, threshold: float) -> float:
    if agents <= traffic:
        return 0.0
    probability_wait = enlang_c(agents, traffic)
    sla = 1.0 - probability_wait * math.exp((traffic - agents) * (threshold / aht))
    return max(0.0, min(1.0, sla))


def fractional_agents(
    service_level_goal: float,
    threshold_seconds: float,
    offered_calls: float,
    aht_seconds: float,
    interval_minutes: float = 30.0,
    occupancy_target: float = 0.85,
) -> float:
    if offered_calls <= 0 or aht_seconds <= 0:
        return 0.0

    calls_per_hours = offered_calls * (60.0 / interval_minutes)
    traffic = calls_per_hours * (aht_seconds / 3600.0)
    agents = max(1, math.ceil(traffic))

    while service_level(agents, traffic, aht_seconds, threshold_seconds) < service_level_goal:
        agents += 1

    previous_agents = agents - 1
    if previous_agents <= 0:
        return float(agents)

    previous_sla = service_level(previous_agents, traffic, aht_seconds, threshold_seconds)
    current_sla = service_level(agents, traffic, aht_seconds, threshold_seconds)

    if current_sla == previous_sla:
        return float(agents)

    fraction = (service_level_goal - previous_sla) / (current_sla - previous_sla)
    return float(previous_agents + fraction)


# ==============================================================================
# 2. DATABASE FETCH FUNCTION
# ==============================================================================
def fetch_forecast_demand_by_range(
    start_date: str,
    end_date: str,
    skills_list: Optional[List[str]] = None,
) -> pd.DataFrame:
    """Selects the required columns from forecast_demand_data filtered by timestamp_local."""
    s_date = f"{str(start_date).strip()[:10]} 00:00:00"
    e_date = f"{str(end_date).strip()[:10]} 23:59:59"

    params: Dict[str, Any] = {"start_ts": s_date, "end_ts": e_date}
    where_clauses = [
        '"timestamp_local" >= :start_ts',
        '"timestamp_local" <= :end_ts',
    ]

    if skills_list:
        clean_skills = [str(s).strip() for s in skills_list]
        placeholders = []
        for i, sk in enumerate(clean_skills):
            pk = f"sk_{i}"
            placeholders.append(f":{pk}")
            params[pk] = sk
        where_clauses.append(f'"ct" IN ({", ".join(placeholders)})')

    query = text(f"""
        SELECT 
            "timestamp_local",
            "offered",
            "service_level_goal_percent",
            "service_level_threshold_seconds",
            "max_occupancy_percent",
            "aht_seconds",
            "asa_seconds",
            "asa_goal_seconds",
            "required_fte",
            "revised_fte"
        FROM forecast_demand_data
        WHERE {" AND ".join(where_clauses)}
    """)

    session = SessionLocal()
    try:
        engine = session.get_bind()
        df = pd.read_sql_query(query, engine, params=params)
        return df
    finally:
        session.close()


# ==============================================================================
# 3. 48-INTERVAL DAILY AGGREGATION (WITH SUMMED FTE TOTALS)
# ==============================================================================
def calculate_daily_forecast_slots(
    df: pd.DataFrame,
    start_date: str,
    end_date: str,
    interval_minutes: int = 30,
) -> List[Dict[str, Any]]:
    """Groups data by Date and produces the exact output structure:

    [
      {
        "Date": "YYYY-MM-DD",
        "total": { ... },
        "slots": [ { ... 48 slots ... } ]
      }
    ]
    """
    date_range = pd.date_range(
        start_date[:10], end_date[:10], freq="D"
    ).strftime("%Y-%m-%d")

    # Generate all 48 half-hour slots
    slot_times = pd.date_range("00:00", "23:59", freq=f"{interval_minutes}min")
    all_48_slots = []
    for tp in slot_times:
        s_str = tp.strftime("%H:%M")
        e_str = (tp + pd.Timedelta(minutes=interval_minutes)).strftime("%H:%M")
        all_48_slots.append((s_str, e_str, f"{s_str}-{e_str}"))

    if not df.empty:
        df["ts_local"] = pd.to_datetime(df["timestamp_local"])
        df["Date"] = df["ts_local"].dt.strftime("%Y-%m-%d")
        df["Slot_Start"] = (
            df["ts_local"]
            .dt.floor(f"{interval_minutes}min")
            .dt.strftime("%H:%M")
        )
        df["Workload"] = df["offered"] * df["aht_seconds"]

    daily_results: List[Dict[str, Any]] = []

    for d in date_range:
        day_df = df[df["Date"] == d] if not df.empty else pd.DataFrame()
        day_slot_results = []

        default_sl_goal = 80.0
        default_thresh = 20.0
        default_occupancy = 85.0

        for s_start, s_end, slot_label in all_48_slots:
            slot_df = (
                day_df[day_df["Slot_Start"] == s_start]
                if not day_df.empty
                else pd.DataFrame()
            )

            if not slot_df.empty and slot_df["offered"].sum() > 0:
                total_offered = float(slot_df["offered"].sum())
                total_workload = float(slot_df["Workload"].sum())
                weighted_aht = (
                    total_workload / total_offered if total_offered > 0 else 0.0
                )

                # SLA Goal
                raw_sl_goal = slot_df["service_level_goal_percent"].dropna()
                sl_goal = (
                    float(raw_sl_goal.iloc[0])
                    if not raw_sl_goal.empty
                    else default_sl_goal
                )
                if sl_goal > 1.0:
                    sl_goal /= 100.0

                # Threshold
                raw_thresh = slot_df["service_level_threshold_seconds"].dropna()
                threshold = (
                    float(raw_thresh.iloc[0])
                    if not raw_thresh.empty
                    else default_thresh
                )

                # Max Occupancy
                raw_occ = slot_df["max_occupancy_percent"].dropna()
                occupancy = (
                    float(raw_occ.iloc[0])
                    if not raw_occ.empty
                    else default_occupancy
                )
                if occupancy > 1.0:
                    occupancy /= 100.0

                # Erlang C Required FTE
                calc_fte = fractional_agents(
                    service_level_goal=sl_goal,
                    threshold_seconds=threshold,
                    offered_calls=total_offered,
                    aht_seconds=weighted_aht,
                    interval_minutes=interval_minutes,
                    occupancy_target=occupancy,
                )

                record = {
                    "Date": d,
                    "Slot Time": slot_label,
                    "Start Slot Time": s_start,
                    "End Slot Time": s_end,
                    "OFFERED (Calls)": round(total_offered, 2),
                    "AHT (Seconds)": round(weighted_aht, 2),
                    "Calculated Required FTE": round(calc_fte, 4),
                    "DB Required FTE": round(float(slot_df["required_fte"].sum()), 4),
                    "DB Revised FTE": round(float(slot_df["revised_fte"].sum()), 4),
                    "Service Level Goal Percent": round(sl_goal * 100.0, 2),
                    "Service Level Threshold Seconds": round(threshold, 2),
                    "Max Occupancy Percent": round(occupancy * 100.0, 2),
                    "ASA Seconds": round(float(slot_df["asa_seconds"].mean()), 2),
                    "ASA Goal Seconds": round(float(slot_df["asa_goal_seconds"].mean()), 2),
                }
            else:
                record = {
                    "Date": d,
                    "Slot Time": slot_label,
                    "Start Slot Time": s_start,
                    "End Slot Time": s_end,
                    "OFFERED (Calls)": 0.0,
                    "AHT (Seconds)": 0.0,
                    "Calculated Required FTE": 0.0,
                    "DB Required FTE": 0.0,
                    "DB Revised FTE": 0.0,
                    "Service Level Goal Percent": default_sl_goal,
                    "Service Level Threshold Seconds": default_thresh,
                    "Max Occupancy Percent": default_occupancy,
                    "ASA Seconds": 0.0,
                    "ASA Goal Seconds": 0.0,
                }

            day_slot_results.append(record)

        # -------------------------------------------------------------
        # COMPUTE DEDICATED "total" DICTIONARY FOR THIS DATE
        # -------------------------------------------------------------
        num_slots = len(day_slot_results)  # 48
        day_total_offered = sum(r["OFFERED (Calls)"] for r in day_slot_results)

        # Volume-weighted AHT
        day_total_workload = sum(
            r["OFFERED (Calls)"] * r["AHT (Seconds)"] for r in day_slot_results
        )
        day_weighted_aht = (
            (day_total_workload / day_total_offered)
            if day_total_offered > 0
            else 0.0
        )

        # SUM of FTE metrics across all 48 half-hour slots
        day_calc_fte_sum = sum(
            r["Calculated Required FTE"] for r in day_slot_results
        )
        day_db_fte_sum = sum(r["DB Required FTE"] for r in day_slot_results)
        day_db_revised_fte_sum = sum(
            r["DB Revised FTE"] for r in day_slot_results
        )

        # Volume-weighted ASA
        if day_total_offered > 0:
            day_total_asa = (
                sum(r["ASA Seconds"] * r["OFFERED (Calls)"] for r in day_slot_results)
                / day_total_offered
            )
            day_total_asa_goal = (
                sum(r["ASA Goal Seconds"] * r["OFFERED (Calls)"] for r in day_slot_results)
                / day_total_offered
            )
        else:
            day_total_asa = 0.0
            day_total_asa_goal = 0.0

        day_sl_goal_avg = (
            sum(r["Service Level Goal Percent"] for r in day_slot_results) / num_slots
        )
        day_threshold_avg = (
            sum(r["Service Level Threshold Seconds"] for r in day_slot_results) / num_slots
        )
        day_occupancy_avg = (
            sum(r["Max Occupancy Percent"] for r in day_slot_results) / num_slots
        )

        total_dict = {
            "OFFERED (Calls)": round(day_total_offered, 2),
            "AHT (Seconds)": round(day_weighted_aht, 2),
            "Calculated Required FTE": round(day_calc_fte_sum / 2, 4),
            "DB Required FTE": round(day_db_fte_sum, 4),
            "DB Revised FTE": round(day_db_revised_fte_sum, 4),
            "Service Level Goal Percent": round(day_sl_goal_avg, 2),
            "Service Level Threshold Seconds": round(day_threshold_avg, 2),
            "Max Occupancy Percent": round(day_occupancy_avg, 2),
            "ASA Seconds": round(day_total_asa, 2),
            "ASA Goal Seconds": round(day_total_asa_goal, 2),
        }

        # Build day entry with explicit Date, total, and slots keys
        daily_results.append({
            "Date": d,
            "total": total_dict,
            "slots": day_slot_results,
        })

    return daily_results


# ==============================================================================
# 4. EXPORT & HELPER FUNCTIONS
# ==============================================================================
def get_forcast_demand_data(
    start_date: str,
    end_date: str,
    skill: list,
    as_json_str: bool = True,
) -> Union[str, List[Dict[str, Any]]]:
    """Fetches data and outputs the structured array with 'Date', 'total', and 'slots'."""
    df_raw = fetch_forecast_demand_by_range(
        start_date=start_date,
        end_date=end_date,
        skills_list=skill,
    )

    structured_data = calculate_daily_forecast_slots(df_raw, start_date, end_date)

    if as_json_str:
        return json.dumps(structured_data, indent=4)
    return structured_data


def save_to_json(
    data: Union[dict, list, str],
    file_path: Union[str, Path],
    indent: int = 4,
) -> str:
    """Saves structured data or JSON string to a file."""
    path = Path(file_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    if isinstance(data, str):
        try:
            parsed = json.loads(data)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(parsed, f, indent=indent, ensure_ascii=False)
        except json.JSONDecodeError:
            with open(path, "w", encoding="utf-8") as f:
                f.write(data)
    else:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)

    print(f"Data successfully saved to: {path}")
    return str(path)
