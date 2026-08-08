import requests
import subprocess
import json

print("\n--- STAGE 5 ---")

print("1. POST /index")
res = requests.post(
    "http://127.0.0.1:8000/index",
    json={"repo_url": "https://github.com/eliasku/unit"}
)
print("Status:", res.status_code)
print(json.dumps(res.json(), indent=2))

print("\n2. POST /ask")
res = requests.post(
    "http://127.0.0.1:8000/ask",
    json={"repo_url": "https://github.com/eliasku/unit", "question": "What does this repo do?"}
)
print("Status:", res.status_code)
print(json.dumps(res.json(), indent=2))

print("\n3. POST /blast-radius")
res = requests.post(
    "http://127.0.0.1:8000/blast-radius",
    json={"repo_url": "https://github.com/eliasku/unit", "targets": ["tests/test.py"]}
)
print("Status:", res.status_code)
print(json.dumps(res.json(), indent=2))

print("\n--- STAGE 6 ---")
print("Running: python3 -m mutagent.run council")
subprocess.run(["python", "-m", "mutagent.run", "council"], check=False)
