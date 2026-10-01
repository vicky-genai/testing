import json
import base64
from unittest.mock import patch, MagicMock
 
DUMMY_DATA_FILE = "mock_data.json"
 
def load_mock_data():
    with open(DUMMY_DATA_FILE, "r") as f:
        return json.load(f)
 
# --- 1. MOCK DATABASE FUNCTIONS ---
def mock_get_work_item_status(work_item_id):
    print(f"[MOCK DB] Fetching status for: {work_item_id}")
    return load_mock_data().get(work_item_id, {}).get("status", "UNKNOWN")
 
def mock_validate_work_item(work_item_id):
    print(f"[MOCK DB] Validating work item: {work_item_id}")
    data = load_mock_data()
    if work_item_id in data:
        item = data[work_item_id]
        item["status"] = "valid"
        return item
    return {"status": "invalid", "reason": "Not found"}
 
def mock_get_incident_id(work_item_id):
    return load_mock_data().get(work_item_id, {}).get("incident_id", "unknown-incident")
 
def mock_generic_insert(*args, **kwargs):
    print(f"[MOCK DB] Skipped DB Insert/Update. Success.")
    return "mocked_id_123"
 
def mock_update_workflow_status(*args, **kwargs):
    print(f"[MOCK DB] Workflow status updated: {kwargs}")
    return {"status": "success"}
 
# --- 2. MOCK CLOUD LOGGING (No real cluster needed!) ---
def mock_fetch_cluster_logs(work_item_details):
    print(f"[MOCK LOGGING] Generating fake CPU Drift logs for LLM to analyze...")
    return {
        "project_id": work_item_details.get("project_id", "gebu-data-ml-day0-01-333910"),
        "location": work_item_details.get("region", "us-central1"),
        "cluster_name": work_item_details.get("cluster_name", "drift-monitoring-cluster"),
        "namespace": work_item_details.get("namespace", "default"),
        "total_entries_scanned": 50,
        "severity_counts": {"ERROR": 2, "WARNING": 5, "CRITICAL": 1, "INFO": 42},
        "keyword_counts": {"CPUThrottlingHigh": 4, "Insufficient cpu": 2, "OOMKilled": 1},
        "raw_logs_payload": (
            "[2026-09-29T10:00:00Z] WARNING: CPUThrottlingHigh detected on node-pool-1\n"
            "[2026-09-29T10:05:00Z] WARNING: CPUThrottlingHigh detected on node-pool-1\n"
            "[2026-09-29T10:10:00Z] ERROR: Pod frontend-app FailedScheduling - Insufficient cpu\n"
            "[2026-09-29T10:11:00Z] ERROR: Pod backend-app FailedScheduling - Insufficient cpu\n"
            "[2026-09-29T10:15:00Z] CRITICAL: OOMKilled backend-service container out of memory"
        )
    }
 
# --- 3. MOCK SMTP / GCS EMAIL NOTIFICATION ---
def mock_send_email(*args, **kwargs):
    print(f"[MOCK NOTIFICATION] Pretending to send email to cluster owner. Success.")
    return {
        "status": "success",
        "recipient": "mock-owner@example.com",
        "notification_id": "mock_notif_123"
    }
 
# --- 4. APPLY PATCHES (Must happen before importing the app) ---
patch('app.cloud_event_handler._get_work_item_status', mock_get_work_item_status).start()
patch('app.tools.tools.validate_work_item', mock_validate_work_item).start()
patch('app.tools.tools._get_incident_id', mock_get_incident_id).start()
patch('app.tools.tools.save_incident_enrichment', mock_generic_insert).start()
patch('app.tools.tools.save_incident_summary', mock_generic_insert).start()
patch('app.tools.tools.record_notification_result', mock_generic_insert).start()
patch('app.tools.tools.set_action_transitions', mock_generic_insert).start()
patch('app.tools.tools.update_work_item_workflow_status', mock_update_workflow_status).start()
 
# Intercept the Logging and Email tools
patch('app.tools.tools.fetch_cluster_logs', mock_fetch_cluster_logs).start()
patch('app.tools.tools.send_incident_email_notification', mock_send_email).start()
 
# Disable SQLAlchemy engine
patch('app.tools.tools.engine', MagicMock()).start()
patch('app.cloud_event_handler.engine', MagicMock()).start()
 
# --- 5. IMPORT APP & RUN TEST ---
from fastapi.testclient import TestClient
from app.fast_api_app import app
 
client = TestClient(app)
 
def run_offline_test():
    print("🚀 Starting 100% Offline Agent Pipeline Test...\n")
    payload = {"work_item_id": "wi_d2c1cc42"}
    base64_payload = base64.b64encode(json.dumps(payload).encode('utf-8')).decode('utf-8')
    pubsub_message = {"message": {"data": base64_payload}}
    response = client.post("/cloudevent", json=pubsub_message)
    print("\n✅ Test Complete!")
    print(f"HTTP Status Code: {response.status_code}")
    print(f"Response Body:\n{json.dumps(response.json(), indent=2)}")
 
if __name__ == "__main__":
    run_offline_test() 


##================================End================================================== 

# INSERT INTO drift_monitor_schema.incidents (
#     incident_id,
#     dedup_key,
#     cluster,
#     nodepool,
#     metric,
#     status,
#     anomaly_start,
#     anomaly_end,
#     drift_summary,
#     transitions,
#     audit
# ) VALUES (
#     'inc_52db62c45',
#     'cloud-gebu-ips:drift-monitoring-cluster:default-pool:kubernetes.io_node_cpu_allocatable_utilization',
#     'drift-monitoring-cluster',
#     'default-pool',
#     'kubernetes.io/node/cpu/allocatable_utilization',
#     'OPEN',
#     '2026-07-06T09:25:00.707368+00:00',
#     NULL,
#     '{"p50_base": 0.35, "p95_base": 0.58, "p50_cur": 0.35, "p95_cur": 0.78, "d_abs": 0.2, "d_rel": 0.3448, "w": 0.2}'::jsonb,
#     '[{"from_state": "NORMAL", "to_state": "DRIFTING", "timestamp": "2026-07-06T09:25:00.707368+00:00", "work_item_id": "wi_d2c1cc45", "metrics": {"p50_cur": 0.35, "p95_cur": 0.78, "d_abs": 0.2, "d_rel": 0.3448, "w": 0.2}}]'::jsonb,
#     '{"created_at": "2026-07-06T09:25:00.707368+00:00", "updated_at": "2026-07-06T09:25:00.707368+00:00", "policy_version": "v1.0"}'::jsonb
# );
 
# INSERT INTO drift_monitor_schema.work_items (
#     work_item_id,
#     incident_id,
#     dedup_key,
#     task_type,
#     status,
#     payload,
#     workflow_enrichment_status,
#     workflow_notification_status,
#     created_at,
#     updated_at
# ) VALUES (
#     'wi_d2c1cc45',
#     'inc_52db62c45',
#     'cloud-gebu-ips:drift-monitoring-cluster:default-pool:kubernetes.io_node_cpu_allocatable_utilization',
#     'ENRICHMENT',
#     'PENDING',
#     '{"triggering_metrics": {"p50_cur": 0.35, "p95_cur": 0.78, "d_abs": 0.2, "d_rel": 0.3448, "w": 0.2}}'::jsonb,
#     'NOT_STARTED',
#     'NOT_SENT',
#     '2026-07-06T09:25:00.707586+00:00',
#     '2026-07-06T09:25:00.707586+00:00'
# );
 
# {
#   "work_item_id": "wi_d2c1cc42"

# } 

