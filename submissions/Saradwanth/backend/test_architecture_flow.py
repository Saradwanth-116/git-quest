import requests
import json
import time
from pathlib import Path

BASE_URL = "http://127.0.0.1:8000"
REPO_URL = "https://github.com/eliasku/unit"
TRACES_DIR = Path(__file__).parent / "mutagent" / "traces"
REPORTS_DIR = Path(__file__).parent / "mutagent" / "reports"

def print_step(title):
    print(f"\n{'='*60}\n[STEP] {title}\n{'='*60}")

def main():
    print_step("1. Indexing Repository")
    print(f"POST /index for {REPO_URL}")
    res = requests.post(f"{BASE_URL}/index", json={"repo_url": REPO_URL})
    print(json.dumps(res.json(), indent=2))

    print_step("2. Testing Feature: Maintainer Health")
    print(f"GET /maintainer-health?repo_url={REPO_URL}")
    res = requests.get(f"{BASE_URL}/maintainer-health?repo_url={REPO_URL}")
    print(json.dumps(res.json(), indent=2))

    print_step("3. Testing Feature: Issue Recommendation")
    print(f"POST /recommend-issue")
    res = requests.post(f"{BASE_URL}/recommend-issue", json={
        "repo_url": REPO_URL,
        "user_profile": "Python developer looking for good first issues"
    })
    print(json.dumps(res.json(), indent=2))

    print_step("4. Verifying Mutagent Traces (Production Telemetry)")
    print("Checking backend/mutagent/traces/ for new telemetry data...\n")
    for trace_file in TRACES_DIR.glob("*.jsonl"):
        with open(trace_file, "r") as f:
            lines = f.readlines()
            print(f"[OK] Found {len(lines)} traces in {trace_file.name}")
            # Print the most recent trace
            latest = json.loads(lines[-1])
            print(f"   Latest latency: {latest['latency_ms']}ms")
            print(f"   Raw output logged: {latest['raw_output'][:100]}...")

    print_step("5. Simulating Mutagent Optimization Cycle")
    print("Writing a mock evaluation report to backend/mutagent/reports/issue_rec.delta.json")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_data = {
        "baseline_score": 0.45,
        "optimized_score": 0.88,
        "delta": 0.43,
        "generations": 5,
        "notes": "Simulated mutagent optimization run"
    }
    with open(REPORTS_DIR / "issue_rec.delta.json", "w") as f:
        json.dump(report_data, f, indent=2)
    print("[OK] Report written!")

    print_step("6. Testing Metrics Dashboard")
    print("GET /metrics (This is what the frontend UI reads)")
    res = requests.get(f"{BASE_URL}/metrics")
    print(json.dumps(res.json(), indent=2))

if __name__ == "__main__":
    main()
