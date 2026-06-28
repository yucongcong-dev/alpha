import json
with open(r"c:\Users\14772\CodeBuddy\20260618230221\alpha\results\model51\test_results.json") as f:
    data = json.load(f)
for r in data["results"]:
    checks = r.get("failed_checks", [])
    sharpe = next((c["value"] for c in checks if c["name"]=="LOW_SHARPE"), "N/A")
    fitness = next((c["value"] for c in checks if c["name"]=="LOW_FITNESS"), "N/A")
    print(f"{r['template_name']:50s} Sharpe={str(sharpe):>7s}  Fitness={str(fitness):>7s}  alpha={r.get('alpha_id','N/A')}")
