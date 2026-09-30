import sys
from pathlib import Path

# Add project root ('cnx_data') to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))


import sys
from pathlib import Path

# Add project root ('cnx_data') to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from datetime import date, datetime, time, timezone
import json
from typing import Any, Dict, List, Optional, Union
import pandas as pd

from db.db_init import SessionLocal, init_db
from db.model import ForecastDemandData

# Ensure table exists
init_db()


# =====================================================================
# 1. ROBUST PARSERS
# =====================================================================
def _parse_dt(val: Any) -> Optional[datetime]:
    """Safely parses datetime strings in format '2026-08-24 08:15:00', ISO, or pandas timestamps."""
    if val is None or pd.isna(val):
        return None
    if isinstance(val, datetime):
        return val

    val_str = str(val).strip()
    if not val_str or val_str.lower() in ("nan", "none", "null", "nat", ""):
        return None
    if val_str.startswith("#"):  # Handles Excel '#ERROR!' artifacts
        return None

    clean_str = val_str.replace("T", " ")
    formats = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
    )
    for fmt in formats:
        try:
            return datetime.strptime(clean_str, fmt)
        except ValueError:
            continue

    try:
        ts = pd.to_datetime(val)
        return ts.to_pydatetime() if not pd.isna(ts) else None
    except Exception:
        return None


def _parse_d(val: Any) -> Optional[date]:
    """Safely parses date strings (e.g. '2026-08-24' or datetime objects)."""
    if val is None or pd.isna(val):
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val

    val_str = str(val).strip()
    if not val_str or val_str.lower() in ("nan", "none", "null", "nat", ""):
        return None
    if val_str.startswith("#"):
        return None

    clean_str = val_str.replace("T", " ")
    formats = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d/%m/%Y",
    )
    for fmt in formats:
        try:
            return datetime.strptime(clean_str, fmt).date()
        except ValueError:
            continue

    try:
        ts = pd.to_datetime(val)
        return ts.date() if not pd.isna(ts) else None
    except Exception:
        return None


def _parse_t(val: Any) -> Optional[time]:
    """Safely parses time values (e.g. '08:30:00', '08:30', or datetime objects)."""
    if val is None or pd.isna(val):
        return None
    if isinstance(val, datetime):
        return val.time()
    if isinstance(val, time):
        return val

    val_str = str(val).strip()
    if not val_str or val_str.lower() in ("nan", "none", "null", "nat", ""):
        return None
    if val_str.startswith("#"):
        return None

    formats = ("%H:%M:%S", "%H:%M")
    for fmt in formats:
        try:
            return datetime.strptime(val_str, fmt).time()
        except ValueError:
            continue

    try:
        ts = pd.to_datetime(val)
        return ts.time() if not pd.isna(ts) else None
    except Exception:
        return None


def _clean_str(val: Any) -> Optional[str]:
    """Filters out '#ERROR!', nulls, or empty string values."""
    if val is None or pd.isna(val):
        return None
    s = str(val).strip()
    return None if s.lower() in ("nan", "none", "null", "") or s.startswith("#") else s


def _clean_float(val: Any, default: float = 0.0) -> float:
    """Safely converts numeric metrics to float."""
    if val is None or pd.isna(val):
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _clean_bool(val: Any, default: Optional[bool] = True) -> Optional[bool]:
    """Safely parses boolean values (accepts 'TRUE', 'FALSE', 1, 0, or boolean types)."""
    if val is None or pd.isna(val):
        return default
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    s = str(val).strip().lower()
    if s in ("true", "1", "yes", "y", "t"):
        return True
    if s in ("false", "0", "no", "n", "f"):
        return False
    return default


# =====================================================================
# 2. BULK INGESTION FUNCTION FOR ForecastDemandData
# =====================================================================
def add_bulk_forecast_demand(
    records: Union[List[Dict[str, Any]], str],
    chunk_size: int = 1000
) -> Dict[str, Any]:
    """
    Bulk inserts JSON records into the ForecastDemandData table.

    Args:
        records: Python list of dicts or raw JSON string.
        chunk_size: Batch size for chunked database commits.
    """
    if isinstance(records, str):
        records = json.loads(records)

    if not records:
        return {
            "status": "success",
            "inserted_count": 0,
            "message": "Empty records list.",
        }

    now_utc = datetime.now(timezone.utc)
    total_inserted = 0

    with SessionLocal() as db:
        try:
            for i in range(0, len(records), chunk_size):
                chunk = records[i : i + chunk_size]
                orm_objects = []

                for item in chunk:
                    # Resolve Primary Timestamps
                    ts_raw = item.get("timestamp") or item.get("Timestamp")
                    parsed_ts = _parse_dt(ts_raw)

                    ts_local_raw = item.get("timestamp_local") or item.get("Timestamp Local")
                    parsed_ts_local = _parse_dt(ts_local_raw) or parsed_ts

                    # Resolve or derive Local Date and Local Time
                    date_raw = item.get("local_date") or item.get("Local Date")
                    parsed_date = _parse_d(date_raw) or (
                        parsed_ts_local.date() if parsed_ts_local else None
                    )

                    time_raw = item.get("local_time") or item.get("Local Time")
                    parsed_time = _parse_t(time_raw) or (
                        parsed_ts_local.time() if parsed_ts_local else None
                    )

                    # Workload calculation fallback (aht_x_offered)
                    offered = _clean_float(item.get("offered") or item.get("Offered"), 0.0)
                    aht = _clean_float(item.get("aht_seconds") or item.get("AHT Seconds"), 0.0)
                    raw_workload = (
                        item.get("aht_x_offered")
                        if "aht_x_offered" in item
                        else item.get("AHT x Offered")
                    )
                    workload = (
                        _clean_float(raw_workload)
                        if raw_workload is not None
                        else (offered * aht)
                    )

                    # Selected Config parser
                    cfg_raw = (
                        item.get("selected_config")
                        if "selected_config" in item
                        else item.get("Selected (Config)")
                    )
                    parsed_cfg = _clean_bool(cfg_raw, default=True)

                    obj = ForecastDemandData(
                        timestamp=parsed_ts,
                        timestamp_local=parsed_ts_local,
                        local_date=parsed_date,
                        local_time=parsed_time,
                        offered=offered,
                        service_level_goal_percent=_clean_float(
                            item.get("service_level_goal_percent") or item.get("Service Level Goal Percent"),
                            default=80.0
                        ),
                        service_level_threshold_seconds=_clean_float(
                            item.get("service_level_threshold_seconds") or item.get("Service Level Threshold Seconds"),
                            default=20.0
                        ),
                        max_occupancy_percent=_clean_float(
                            item.get("max_occupancy_percent") or item.get("Max Occupancy Percent"),
                            default=90.0
                        ),
                        aht_seconds=aht,
                        asa_seconds=_clean_float(
                            item.get("asa_seconds") or item.get("ASA Seconds"),
                            default=0.0
                        ),
                        asa_goal_seconds=_clean_float(
                            item.get("asa_goal_seconds") or item.get("ASA Goal Seconds"),
                            default=0.0
                        ),
                        required_fte=_clean_float(
                            item.get("required_fte") or item.get("Required FTE"),
                            default=0.0
                        ),
                        revised_fte=_clean_float(
                            item.get("revised_fte") or item.get("Revised FTE"),
                            default=0.0
                        ),
                        snapshot_type_description=_clean_str(
                            item.get("snapshot_type_description") or item.get("Snapshot Type Description") or "Current"
                        ),
                        timezone=_clean_str(item.get("timezone") or item.get("Timezone")),
                        ct_id=_clean_str(item.get("ct_id") or item.get("CT ID")),
                        ct=_clean_str(item.get("ct") or item.get("CT")),
                        customer_id=_clean_str(item.get("customer_id") or item.get("Customer ID")),
                        wfm_server=_clean_str(item.get("wfm_server") or item.get("WFM Server")),
                        job_system_id=_clean_str(item.get("job_system_id") or item.get("Job System ID")),
                        job_system=_clean_str(item.get("job_system") or item.get("Job System")),
                        selected_config=parsed_cfg,
                        aht_x_offered=workload,
                        insert_timestamp=_parse_dt(
                            item.get("insert_timestamp") or item.get("Insert Timestamp")
                        ) or now_utc,
                        update_timestamp=_parse_dt(
                            item.get("update_timestamp") or item.get("Update Timestamp")
                        ) or now_utc,
                    )
                    orm_objects.append(obj)

                db.bulk_save_objects(orm_objects)
                db.commit()
                total_inserted += len(orm_objects)

            return {
                "status": "success",
                "message": f"Successfully inserted {total_inserted} forecast demand records.",
                "inserted_count": total_inserted,
            }

        except Exception as e:
            db.rollback()
            return {
                "status": "error",
                "message": f"Failed during bulk insert: {str(e)}",
                "inserted_count": total_inserted,
            }
