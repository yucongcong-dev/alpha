import json
from pathlib import Path

results_file = Path(__file__).parent.parent / "results" / "pv1_test_results_analysis.json"
data = json.loads(results_file.read_text(encoding="utf-8"))
print(f"Tested: {data['tested']}")
print(f"Submittable: {data['submittable_count']}")
print(f"Errors: {data['error_count']}")
print(f"Near pass count: {len(data.get('near_pass_summary', []))}")

if data.get('near_pass_summary'):
    print("\nTop near-pass candidates:")
    for np in data['near_pass_summary'][:3]:
        print(f"  - {np['field_id']}:{np['template_name']} score={np['score']:.3f}")
