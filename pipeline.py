import sys
from pathlib import Path

# Add project root ('cnx_data') to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))


from tools.schedule_data_format import get_schedle_data
from  tools.supply_cat_pc import format_comprehensive_schedule_metrics

# inputs
START_DATE = "2026-08-24"
END_DATE = "2026-08-25"
SKILLS = ["Call Type 1", "Call Type 2", "Call Type 3", "Call Type 4"]

# scheduled pipeline
def get_schdeduled_data(start_date: str, end_date: str, skill: list):
    data = get_schedle_data(start_date,end_date,skill)
    responce  = format_comprehensive_schedule_metrics(data)
    return responce

raw_summary = get_schdeduled_data(
    START_DATE,
    END_DATE,
    SKILLS) 


from tools.summary_data import extract_schedule_daily_totals
from tools.shrinkage_matrix_data import generate_shrinkage_matrix_json
from tools.slot_planned_activities import apply_daily_scaling_factor

# Summary Tab Data
summarydata = extract_schedule_daily_totals(
    raw_summary)

# Input
custom_assumptions = {
    "PLANNED ABSENCE": 0.00,
    "ABSENCE": 0.20,  # 20%
    "HOLIDAY PAID": 0.06,  # 6%
    "HOLIDAY UNPAID": 0.00,
}

# Assumption Tab Data
shrinkage_matrix = generate_shrinkage_matrix_json(
    schedule_summary_payload=summarydata,
    assumptions_input=custom_assumptions,
    as_json_str=True,
)

# Schedule Tab Data
schedule_data = apply_daily_scaling_factor(
    schedule_data=raw_summary,
    shrinkage_matrix=shrinkage_matrix,
)

from tools.forecast_data_format import get_forcast_demand_data

# forecast Tab Data
forcast_data = get_forcast_demand_data(
    START_DATE, 
    END_DATE, SKILLS,
     as_json_str=True)



# Creatting the supply Vs Demand Tab Data
from tools.supply_vs_demand import generate_supply_vs_demand_table


supply_vs_demand_data = generate_supply_vs_demand_table(
    forecast_data=forcast_data,
    schedule_with_planned=schedule_data,
    as_json_str=True,
    as_dataframe=False,
)


print(supply_vs_demand_data)



