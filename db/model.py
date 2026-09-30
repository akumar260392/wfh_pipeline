# Imports

from db.db_init import Base
from sqlalchemy import Column, Integer, Float, String, DateTime, Date, Text,Time,Boolean



class ScheduleData(Base):
    __tablename__ = "schedule_data"

    # Primary Key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Core Timestamps & Shift Date
    timestamp = Column("Timestamp", DateTime, nullable=True, index=True)
    shift_date = Column("Shift Date", Date, nullable=False, index=True)
    start_timestamp = Column("Start Timestamp", DateTime, nullable=True)
    end_timestamp = Column("End Timestamp", DateTime, nullable=True)
    start_timestamp_local = Column(
        "Start Timestamp Local", DateTime, nullable=True, index=True
    )
    end_timestamp_local = Column(
        "End Timestamp Local", DateTime, nullable=True, index=True
    )

    # Agent Identification & System IDs
    person_id = Column("Person ID", String(50), nullable=True, index=True)
    login_id = Column("Login ID", String(50), nullable=True, index=True)
    customer_id = Column("Customer ID", String(50), nullable=True)
    wfm_server = Column("WFM Server", String(50), nullable=True)
    job_system_id = Column("Job System ID", String(50), nullable=True)
    job_system = Column("Job System", String(100), nullable=True)

    # Shift / Activity / Exception Breakdown
    exception_name = Column("Exception Name", String(150), nullable=True)
    exception_group = Column("Exception Group", String(150), nullable=True)
    total_minutes = Column("Total Minutes", Float, nullable=True, default=0.0)
    exception_type = Column("Exception_Type", String(100), nullable=True)
    primary_category = Column("Primary Category", String(100), nullable=True)
    grouping = Column("Grouping", String(100), nullable=True)
    selected_config = Column("Selected (Config)", String(100), nullable=True)

    # Management Unit (MU) & Timezone
    timezone = Column("Timezone", String(100), nullable=True)
    mu_id = Column("MU ID", String(50), nullable=True)
    mu = Column("MU", String(150), nullable=True)

    # Audit Timestamps
    insert_timestamp = Column("Insert Timestamp", DateTime, nullable=True)
    update_timestamp = Column("Update Timestamp", DateTime, nullable=True)

    # Agent Demographics & Profile
    person = Column("Person", String(150), nullable=True)
    person_preferred_name = Column(
        "Person Preferred Name", String(150), nullable=True
    )
    email_address = Column("Email Address", String(200), nullable=True)
    job_title = Column("Job Title", String(150), nullable=True)
    job_category = Column("Job Category", String(100), nullable=True)
    person_timezone = Column("Person Timezone", String(150), nullable=True)

    # Skills & Business Lines
    primary_ct_skill = Column("Primary CT_Skill", String(150), nullable=True)
    ecp_lob = Column("ECP LOB", String(150), nullable=True)

    # Serial / Auxiliary Export Columns
    start_local_serial = Column(
        "Start Local (Serial)", String(100), nullable=True
    )
    end_local_serial = Column("End Local (Serial)", String(100), nullable=True)

class ForecastDemandData(Base):
    __tablename__ = "forecast_demand_data"

    # Primary Key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Core Timestamps & Local Date/Time
    timestamp = Column(DateTime, nullable=True, index=True)
    timestamp_local = Column(DateTime, nullable=True)
    local_date = Column(Date, nullable=True, index=True)
    local_time = Column(Time, nullable=True)

    # Workload, Forecast & FTE Metrics
    offered = Column(Float, nullable=True, default=0.0)
    service_level_goal_percent = Column(Float, nullable=True)
    service_level_threshold_seconds = Column(Float, nullable=True)
    max_occupancy_percent = Column(Float, nullable=True)
    aht_seconds = Column(Float, nullable=True, default=0.0)
    asa_seconds = Column(Float, nullable=True, default=0.0)
    asa_goal_seconds = Column(Float, nullable=True, default=0.0)
    required_fte = Column(Float, nullable=True, default=0.0)
    revised_fte = Column(Float, nullable=True, default=0.0)
    aht_x_offered = Column(Float, nullable=True, default=0.0)

    # Call Type & Configuration
    ct_id = Column(String(50), nullable=True, index=True)
    ct = Column(String(150), nullable=True)
    snapshot_type_description = Column(String(100), nullable=True)
    selected_config = Column(Boolean, nullable=True, default=True)

    # System & Server Identifiers
    timezone = Column(String(100), nullable=True)
    customer_id = Column(String(50), nullable=True)
    wfm_server = Column(String(50), nullable=True)
    job_system_id = Column(String(50), nullable=True)
    job_system = Column(String(100), nullable=True)

    # Audit Timestamps
    insert_timestamp = Column(DateTime, nullable=True)
    update_timestamp = Column(DateTime, nullable=True)



# class ScheduleDataInterval(Base):
#     __tablename__ = "schedule_data_30min_interval"

#     # Primary Key
#     id = Column(Integer, primary_key=True, index=True, autoincrement=True)

#     # Core Timestamps & Shift Date
#     timestamp = Column("Timestamp", DateTime, nullable=True, index=True)
#     shift_date = Column("Shift Date", Date, nullable=False, index=True)
#     start_timestamp = Column("Start Timestamp", DateTime, nullable=True)
#     end_timestamp = Column("End Timestamp", DateTime, nullable=True)
#     start_timestamp_local = Column(
#         "Start Timestamp Local", DateTime, nullable=True
#     )
#     end_timestamp_local = Column("End Timestamp Local", DateTime, nullable=True)

#     # Agent Identification & System IDs
#     person_id = Column("Person ID", String(50), nullable=True, index=True)
#     login_id = Column("Login ID", String(50), nullable=True, index=True)
#     customer_id = Column("Customer ID", String(50), nullable=True)
#     wfm_server = Column("WFM Server", String(50), nullable=True)
#     job_system_id = Column("Job System ID", String(50), nullable=True)
#     job_system = Column("Job System", String(100), nullable=True)

#     # Shift / Activity / Exception Breakdown
#     exception_name = Column("Exception Name", String(150), nullable=True)
#     exception_group = Column("Exception Group", String(150), nullable=True)
#     total_minutes = Column("Total Minutes", Float, nullable=True, default=0.0)
#     exception_type = Column("Exception_Type", String(100), nullable=True)
#     primary_category = Column("Primary Category", String(100), nullable=True)
#     grouping = Column("Grouping", String(100), nullable=True)
#     selected_config = Column("Selected (Config)", String(100), nullable=True)

#     # Management Unit (MU) & Timezone
#     timezone = Column("Timezone", String(100), nullable=True)
#     mu_id = Column("MU ID", String(50), nullable=True)
#     mu = Column("MU", String(150), nullable=True)

#     # Audit Timestamps
#     insert_timestamp = Column("Insert Timestamp", DateTime, nullable=True)
#     update_timestamp = Column("Update Timestamp", DateTime, nullable=True)

#     # Agent Demographics & Profile
#     person = Column("Person", String(150), nullable=True)
#     person_preferred_name = Column(
#         "Person Preferred Name", String(150), nullable=True
#     )
#     email_address = Column("Email Address", String(200), nullable=True)
#     job_title = Column("Job Title", String(150), nullable=True)
#     job_category = Column("Job Category", String(100), nullable=True)
#     person_timezone = Column("Person Timezone", String(150), nullable=True)

#     # Skills & Business Lines
#     primary_ct_skill = Column("Primary CT_Skill", String(150), nullable=True)
#     ecp_lob = Column("ECP LOB", String(150), nullable=True)

#     # Serial / Auxiliary Export Columns
#     start_local_serial = Column(
#         "Start Local (Serial)", String(100), nullable=True
#     )
#     end_local_serial = Column("End Local (Serial)", String(100), nullable=True)