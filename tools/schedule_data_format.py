import sys
from pathlib import Path

# Add project root ('cnx_data') to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import json
import numpy as np
import pandas as pd
from typing import List, Optional,Any,Dict,Union
from sqlalchemy import create_engine, text

from db.db_init import SessionLocal, init_db
from db.model import ScheduleData


# ==============================================================================
# 30-MINUTE INTERVAL EXPANSION (PRESERVING ALL COLUMNS)
# ==============================================================================
def split_schedule_into_30min_slots(
    df: pd.DataFrame,
    start_col: str = "Start Timestamp Local",
    end_col: str = "End Timestamp Local"
) -> pd.DataFrame:
    """
    Takes the Schedule_Data DataFrame with all original columns intact,
    splits each row across 30-minute interval slots, and appends:
      - 'Slot Date'
      - 'Start Slot Time'
      - 'End Slot Time'
      - 'Slot Duration (Mins)'
    """
    if df.empty:
        return df.copy()

    data = df.copy()

    # Parse timestamps for calculation
    start_dt = pd.to_datetime(data[start_col])
    end_dt = pd.to_datetime(data[end_col])

    # Boundaries for slot intervals
    data["_start_dt"] = start_dt
    data["_end_dt"] = end_dt
    data["_floor_start"] = start_dt.dt.floor("30min")
    data["_ceil_end"] = end_dt.dt.ceil("30min")

    # Generate slot intervals for each row
    def generate_slots(row):
        s = row["_floor_start"]
        e = row["_ceil_end"]
        if pd.isna(s) or pd.isna(e) or s >= e:
            return []
        return list(pd.date_range(start=s, end=e, freq="30min", inclusive="left"))

    data["_slot_start_dt"] = data.apply(generate_slots, axis=1)

    # Explode slots into multiple rows
    exploded = data.explode("_slot_start_dt")
    exploded = exploded.dropna(subset=["_slot_start_dt"]).copy()
    
    if exploded.empty:
        return df.copy()

    exploded.reset_index(drop=True, inplace=True)

    # Calculate individual 30-min slot boundaries
    exploded["_slot_start_dt"] = pd.to_datetime(exploded["_slot_start_dt"])
    exploded["_slot_end_dt"] = exploded["_slot_start_dt"] + pd.Timedelta(minutes=30)

    # Active overlap = MIN(End, Slot End) - MAX(Start, Slot Start)
    act_start = np.maximum(exploded["_start_dt"], exploded["_slot_start_dt"])
    act_end = np.minimum(exploded["_end_dt"], exploded["_slot_end_dt"])

    # Overlap duration in minutes
    duration = (act_end - act_start).dt.total_seconds() / 60.0
    exploded["Slot Duration (Mins)"] = duration.clip(lower=0.0)

    # Drop zero/negative duration slots if the shift just touched the boundary
    exploded = exploded[exploded["Slot Duration (Mins)"] > 0].copy()
    exploded.reset_index(drop=True, inplace=True)

    # Append new slot columns
    exploded["Slot Date"] = exploded["_slot_start_dt"].dt.strftime("%Y-%m-%d")
    exploded["Start Slot Time"] = exploded["_slot_start_dt"].dt.strftime("%H:%M")
    exploded["End Slot Time"] = exploded["_slot_end_dt"].dt.strftime("%H:%M")

    # Clean up internal temporary columns only
    temp_cols = ["_start_dt", "_end_dt", "_floor_start", "_ceil_end", "_slot_start_dt", "_slot_end_dt"]
    exploded.drop(columns=temp_cols, inplace=True, errors="ignore")

    return exploded


# ==============================================================================
# SAFE DATABASE INSERTER (Prevents NOT NULL constraint failure)
# ==============================================================================
def insert_dataframe_to_db(df: pd.DataFrame, session):
    """
    Safely inserts records into DB, dropping rows where 'Shift Date' is NaN/None.
    """
    # Filter out empty records that cause SQLite IntegrityError
    valid_df = df.dropna(subset=["Shift Date"]).copy()
    
    if valid_df.empty:
        print("No valid rows to insert.")
        return

    # Replace remaining NaN with None so SQLAlchemy handles NULLs appropriately
    records = valid_df.where(pd.notnull(valid_df), None).to_dict(orient="records")
    
    # Bulk insert
    session.bulk_insert_mappings(ScheduleData, records)
    session.commit()
    print(f"Successfully inserted {len(records)} records.")



def fetch_schedule_by_date(
    shift_date: str,
    date_col: str = "Shift Date",
    skills_list: Optional[List[str]] = None
) -> pd.DataFrame:
    """
    Fetches all columns from schedule_data for a specified date and optional skills filter.

    :param shift_date: Target date string, formatted as 'YYYY-MM-DD' (e.g., '2026-08-24')
    :param date_col: Column to filter by (defaults to 'Shift Date')
    :param skills_list: Optional list of skills, e.g. ['Call Type 1', 'Call Type 2']
    :return: pd.DataFrame containing all matching rows and columns
    """
    date_prefix = f"{str(shift_date).strip()[:10]}%"
    params = {"date_prefix": date_prefix}

    # Base WHERE clause
    where_clauses = [f'"{date_col}" LIKE :date_prefix']

    # Dynamically bind skills if provided
    if skills_list:
        clean_skills = [str(s).strip() for s in skills_list]
        skill_placeholders = []
        for i, skill in enumerate(clean_skills):
            param_key = f"skill_{i}"
            skill_placeholders.append(f":{param_key}")
            params[param_key] = skill

        where_clauses.append(f'"Primary CT_Skill" IN ({", ".join(skill_placeholders)})')

    query = text(f"""
        SELECT *
        FROM schedule_data
        WHERE {" AND ".join(where_clauses)}
    """)

    session = SessionLocal()
    try:
        engine = session.get_bind()
        df = pd.read_sql_query(query, engine, params=params)
        return df
    finally:
        session.close()


def fetch_schedule_by_date_range(
    start_date: str,
    end_date: str,
    date_col: str = "Shift Date",
    skills_list: Optional[List[str]] = None
) -> pd.DataFrame:
    """
    Fetches all columns from schedule_data between two dates (inclusive) and optional skills filter.

    :param start_date: 'YYYY-MM-DD' (e.g., '2026-08-24')
    :param end_date: 'YYYY-MM-DD' (e.g., '2026-08-25')
    :param date_col: Column to filter by (defaults to 'Shift Date')
    :param skills_list: Optional list of skills, e.g. ['Call Type 1', 'Call Type 2']
    :return: pd.DataFrame containing all matching rows and columns
    """
    s_date = str(start_date).strip()[:10]
    e_date = f"{str(end_date).strip()[:10]}T23:59:59"

    params = {"s_date": s_date, "e_date": e_date}

    # Base WHERE clause
    where_clauses = [
        f'"{date_col}" >= :s_date',
        f'"{date_col}" <= :e_date'
    ]

    # Dynamically bind skills if provided
    if skills_list:
        clean_skills = [str(s).strip() for s in skills_list]
        skill_placeholders = []
        for i, skill in enumerate(clean_skills):
            param_key = f"skill_{i}"
            skill_placeholders.append(f":{param_key}")
            params[param_key] = skill

        where_clauses.append(f'"Primary CT_Skill" IN ({", ".join(skill_placeholders)})')

    query = text(f"""
        SELECT *
        FROM schedule_data
        WHERE {" AND ".join(where_clauses)}
    """)

    session = SessionLocal()
    try:
        engine = session.get_bind()
        df = pd.read_sql_query(query, engine, params=params)
        return df
    finally:
        session.close()



def get_date_range_slot_summary(
    df_expanded: pd.DataFrame,
    start_date: str,
    end_date: str
) -> dict:
    """
    Summarizes minutes for all 48 30-minute intervals across each day in a date range.
    Provides separate breakdowns for Primary Category and Grouping.

    :param df_expanded: DataFrame output from split_schedule_into_30min_slots()
    :param start_date: 'YYYY-MM-DD' (e.g., '2026-08-24')
    :param end_date: 'YYYY-MM-DD' (e.g., '2026-08-25')
    :return: Dictionary containing date-wise summaries of all 48 slots
    """
    s_date = str(start_date).strip()[:10]
    e_date = str(end_date).strip()[:10]

    # 1. Filter DataFrame for the requested date range
    range_mask = (df_expanded["Slot Date"] >= s_date) & (df_expanded["Slot Date"] <= e_date)
    range_df = df_expanded[range_mask].copy()

    # 2. Extract unique categories across the entire date range
    unique_primary_categories = sorted(
        [cat for cat in range_df["Primary Category"].dropna().unique().tolist() if str(cat).strip()]
    )
    unique_groupings = sorted(
        [grp for grp in range_df["Grouping"].dropna().unique().tolist() if str(grp).strip()]
    )

    # 3. Generate all 48 half-hour slots template (00:00 to 23:30)
    time_points = pd.date_range("00:00", "23:59", freq="30min")
    all_slots = []
    for tp in time_points:
        start_str = tp.strftime("%H:%M")
        end_str = (tp + pd.Timedelta(minutes=30)).strftime("%H:%M")
        all_slots.append((start_str, end_str))

    # 4. Generate all calendar days in range
    calendar_days = pd.date_range(start=s_date, end=e_date, freq="D").strftime("%Y-%m-%d").tolist()

    # 5. Build slot breakdowns for each day
    daily_summaries = []

    for current_day in calendar_days:
        day_df = range_df[range_df["Slot Date"] == current_day]
        slots_output = []

        for start_t, end_t in all_slots:
            slot_label = f"{start_t}-{end_t}"
            slot_rows = day_df[
                (day_df["Start Slot Time"] == start_t) & 
                (day_df["End Slot Time"] == end_t)
            ]

            # Primary Category breakdown (defaults to 0.0 if not present in slot)
            cat_minutes = {}
            for cat in unique_primary_categories:
                mins = slot_rows[slot_rows["Primary Category"] == cat]["Slot Duration (Mins)"].sum()
                cat_minutes[cat] = round(float(mins), 2)

            # Grouping breakdown (defaults to 0.0 if not present in slot)
            grouping_minutes = {}
            for grp in unique_groupings:
                mins = slot_rows[slot_rows["Grouping"] == grp]["Slot Duration (Mins)"].sum()
                grouping_minutes[grp] = round(float(mins), 2)

            # Extract Back Office specifically
            back_office_mins = slot_rows[
                slot_rows["Grouping"].astype(str).str.strip().str.lower() == "back office"
            ]["Slot Duration (Mins)"].sum()

            # Total slot minutes
            total_slot_mins = slot_rows["Slot Duration (Mins)"].sum()

            slots_output.append({
                "date": current_day,
                "slot_time": slot_label,
                "start_time": start_t,
                "end_time": end_t,
                "total_minutes": round(float(total_slot_mins), 2),
                "back_office_minutes": round(float(back_office_mins), 2),
                "primary_categories": cat_minutes,
                "groupings": grouping_minutes
            })

        daily_summaries.append({
            "date": current_day,
            "slots": slots_output
        })

    return {
        "start_date": s_date,
        "end_date": e_date,
        "unique_primary_categories": unique_primary_categories,
        "unique_groupings": unique_groupings,
        "daily_data": daily_summaries
    }




def get_schedle_data(
    start_date: str,
    end_date: str,
    skill: list,
    as_json_str: bool = True,
) -> Union[str, Dict[str, Any]]:
    """Fetches schedule data, splits into 30-min intervals, aggregates daily slot

    summaries, and returns the result in JSON format.

    :param start_date: 'YYYY-MM-DD' (e.g. '2026-08-24')
    :param end_date: 'YYYY-MM-DD' (e.g. '2026-08-25')
    :param skill: List of skills/CT (e.g. ['Call Type 1', 'Call Type 2'])
    :param as_json_str: If True, returns a pretty-printed JSON string; if False,
      returns a Python dict.
    :return: JSON formatted string or Python dictionary.
    """
    # 1. Fetch raw schedule data from DB
    df_raw = fetch_schedule_by_date_range(
        start_date=start_date,
        end_date=end_date,
        skills_list=skill,
    )

    # 2. Expand rows into 30-minute intervals
    df_expanded = split_schedule_into_30min_slots(df_raw)

    # 3. Aggregate across all 48 slots per day
    daily_summary = get_date_range_slot_summary(
        df_expanded=df_expanded,
        start_date=start_date,
        end_date=end_date,
    )

    # 4. Return as JSON string or raw Python dictionary
    if as_json_str:
        return json.dumps(daily_summary, indent=4)
    return daily_summary




def save_to_json(
    data: Union[pd.DataFrame, dict, list, str],
    file_path: Union[str, Path],
    indent: int = 4
) -> str:
    """
    Saves a pandas DataFrame, Python dictionary, list, or JSON string to a JSON file.
    Creates parent directories automatically if they do not exist.
    """
    path = Path(file_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    # 1. If it's a pandas DataFrame
    if isinstance(data, pd.DataFrame):
        data.to_json(path, orient="records", date_format="iso", indent=indent)
    
    # 2. If it's a JSON string
    elif isinstance(data, str):
        try:
            parsed = json.loads(data)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(parsed, f, indent=indent, ensure_ascii=False)
        except json.JSONDecodeError:
            with open(path, "w", encoding="utf-8") as f:
                f.write(data)
                
    # 3. If it's a Python dict or list
    else:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)

    print(f"Data successfully saved to: {path}")
    return str(path)







# print(enriched_schedule)

# print(df_table)




# output_filename = f"scheduled_demand_summary{"2026-08-24"}_to_{"2026-08-25"}.json"
# save_to_json(responce, output_filename)

