"""清理 model51 旧结果，只保留有效模拟"""
import json
from pathlib import Path

results_dir = Path(r"c:\Users\14772\CodeBuddy\20260618230221\alpha\results\model51")

# 1. 清理 test_results.json
with open(results_dir / "test_results.json") as f:
    data = json.load(f)

simulated = [r for r in data["results"] if r.get("status") == "simulated"]
errors = [r for r in data["results"] if r.get("status") == "error"]

print(f"Total results: {len(data['results'])}")
print(f"Simulated (keep): {len(simulated)}")
for s in simulated:
    print(f"  - {s['template_name']}: alpha_id={s.get('alpha_id')}, sharpe=N/A")
print(f"Errors (remove): {len(errors)}")

data["results"] = simulated
data["tested"] = len(simulated)
data["errors"] = 0
data["submittable"] = 0
data["submitted"] = 0

with open(results_dir / "test_results.json", "w") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print(f"\nCleaned test_results.json: {len(simulated)} results kept")

# 2. 删除旧的 analysis 文件（下次会自动重新生成）
for fname in ["test_results_analysis.json"]:
    fpath = results_dir / fname
    if fpath.exists():
        fpath.unlink()
        print(f"Deleted: {fname}")

print("\nDone. Ready to restart.")
