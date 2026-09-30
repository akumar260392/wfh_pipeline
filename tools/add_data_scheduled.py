import sys
from pathlib import Path

# Add project root ('cnx_data') to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from datetime import date, datetime, timezone
import json
from typing import Any, Dict, List, Optional, Union
import pandas as pd
from sqlalchemy.dialects.sqlite import insert  # or from sqlalchemy import insert

from db.db_init import SessionLocal, init_db
from db.model import ScheduleData

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
  if not val_str or val_str.lower() in ("nan", "none", "null", "nat"):
    return None

  clean_str = val_str.replace("T", " ")
  formats = (
      "%Y-%m-%d %H:%M:%S",
      "%Y-%m-%d %H:%M",
      "%Y-%m-%d",
      "%Y/%m/%d %H:%M:%S",
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
  """Safely parses shift_date (e.g. '2026-08-24 00:00:00' or '2026-08-24')."""
  if val is None or pd.isna(val):
    return None
  if isinstance(val, datetime):
    return val.date()
  if isinstance(val, date):
    return val

  val_str = str(val).strip()
  if not val_str or val_str.lower() in ("nan", "none", "null", "nat"):
    return None

  clean_str = val_str.replace("T", " ")
  formats = (
      "%Y-%m-%d %H:%M:%S",
      "%Y-%m-%d %H:%M",
      "%Y-%m-%d",
      "%Y/%m/%d",
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


def _clean_str(val: Any) -> Optional[str]:
  if val is None or pd.isna(val):
    return None
  s = str(val).strip()
  return None if s.lower() in ("nan", "none", "null", "") else s


def _clean_float(val: Any, default: float = 0.0) -> float:
  if val is None or pd.isna(val):
    return default
  try:
    return float(val)
  except (ValueError, TypeError):
    return default


# =====================================================================
# 2. BULK INGESTION FUNCTION FOR ScheduleData
# =====================================================================
def add_bulk_data(
    records: Union[List[Dict[str, Any]], str], chunk_size: int = 1000
) -> Dict[str, Any]:
  """Bulk inserts JSON records into ScheduleData table.

  Args:
      records: Either a Python list of dicts, or a raw JSON string.
      chunk_size: Batch size for chunked database commits.
  """
  # If raw JSON string is passed, parse it
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
          # Extract shift_date safely
          shift_date_raw = item.get("shift_date") or item.get("Shift Date")
          parsed_shift = _parse_d(shift_date_raw)

          # Fallback to date from start timestamp if shift_date is missing
          if parsed_shift is None:
            parsed_shift = _parse_d(
                item.get("start_timestamp_local")
                or item.get("Start Timestamp Local")
            )

          if parsed_shift is None:
            raise ValueError(
                f"Missing or invalid shift_date for person {item.get('person')} / {item.get('person_id')}"
            )

          # Handle boolean / string config
          cfg = item.get("selected_config", item.get("Selected (Config)"))
          cfg_str = str(cfg) if cfg is not None else None

          obj = ScheduleData(
              timestamp=_parse_dt(item.get("timestamp")),
              shift_date=parsed_shift,
              start_timestamp=_parse_dt(item.get("start_timestamp")),
              end_timestamp=_parse_dt(item.get("end_timestamp")),
              start_timestamp_local=_parse_dt(
                  item.get("start_timestamp_local")
              ),
              end_timestamp_local=_parse_dt(item.get("end_timestamp_local")),
              person_id=_clean_str(item.get("person_id")),
              login_id=_clean_str(item.get("login_id")),
              customer_id=_clean_str(item.get("customer_id")),
              wfm_server=_clean_str(item.get("wfm_server")),
              job_system_id=_clean_str(item.get("job_system_id")),
              job_system=_clean_str(item.get("job_system")),
              exception_name=_clean_str(item.get("exception_name")),
              exception_group=_clean_str(item.get("exception_group")),
              total_minutes=_clean_float(item.get("total_minutes", 0.0)),
              exception_type=_clean_str(item.get("exception_type")),
              primary_category=_clean_str(item.get("primary_category")),
              grouping=_clean_str(item.get("grouping")),
              selected_config=cfg_str,
              timezone=_clean_str(item.get("timezone")),
              mu_id=_clean_str(item.get("mu_id")),
              mu=_clean_str(item.get("mu")),
              insert_timestamp=_parse_dt(item.get("insert_timestamp"))
              or now_utc,
              update_timestamp=_parse_dt(item.get("update_timestamp"))
              or now_utc,
              person=_clean_str(item.get("person")),
              person_preferred_name=_clean_str(
                  item.get("person_preferred_name")
              ),
              email_address=_clean_str(item.get("email_address")),
              job_title=_clean_str(item.get("job_title")),
              job_category=_clean_str(item.get("job_category")),
              person_timezone=_clean_str(item.get("person_timezone")),
              primary_ct_skill=_clean_str(item.get("primary_ct_skill")),
              ecp_lob=_clean_str(item.get("ecp_lob")),
              start_local_serial=_clean_str(item.get("start_local_serial")),
              end_local_serial=_clean_str(item.get("end_local_serial")),
          )
          orm_objects.append(obj)

        db.bulk_save_objects(orm_objects)
        db.commit()
        total_inserted += len(orm_objects)

      return {
          "status": "success",
          "message": f"Successfully inserted {total_inserted} schedule records.",
          "inserted_count": total_inserted,
      }

    except Exception as e:
      db.rollback()
      return {
          "status": "error",
          "message": f"Failed during bulk insert: {str(e)}",
          "inserted_count": total_inserted,
      }


# # =====================================================================
# # 3. DIRECT EXECUTION TEST
# # =====================================================================
# if __name__ == "__main__":
#   # Your exact JSON data
#   json_data = [
#     {
#     "timestamp": "2026-08-24 07:29:00",
#     "shift_date": "2026-08-24 00:00:00",
#     "start_timestamp": "2026-08-24 07:00:00",
#     "end_timestamp": "2026-08-24 07:29:00",
#     "start_timestamp_local": "2026-08-24 09:00:00",
#     "end_timestamp_local": "2026-08-24 09:29:00",
#     "person_id": "103057461",
#     "login_id": "3045815",
#     "exception_name": "Late-Leave Early",
#     "exception_group": "Unpaid / Unexpected Absence",
#     "total_minutes": 29,
#     "timezone": "Africa/Johannesburg",
#     "mu_id": "266",
#     "mu": "Client X Ncondo Durban ZAF",
#     "customer_id": "1",
#     "wfm_server": "NICE04",
#     "job_system_id": "351764505",
#     "job_system": "NICE04-1",
#     "insert_timestamp": "2026-09-01 08:16:32",
#     "update_timestamp": "2026-09-01 08:16:32",
#     "person": "Agent 1",
#     "person_preferred_name": "Agent 1",
#     "email_address": "agent1@cnx.com",
#     "job_title": "Advisor I, Customer Service",
#     "job_category": "Agent",
#     "person_timezone": "GMT+02:00 South Africa Standard Time (Johannesburg)",
#     "primary_ct_skill": "Call Type 1",
#     "ecp_lob": "",
#     "exception_type": "Absence",
#     "primary_category": "Absence",
#     "grouping": "Absence",
#     "selected_config": True,
#     "start_local_serial": "2026-08-24 09:00:00",
#     "end_local_serial": "2026-08-24 09:29:00"
#   },
#   ]

#   # Execute bulk insert
#   res = add_bulk_data(json_data)
#   print(json.dumps(res, indent=2))


