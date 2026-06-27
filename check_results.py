import json

data = json.load(open('results/pv1_test_results_analysis.json'))
print(f"Tested: {data['tested']}")
print(f"Submittable: {data['submittable_count']}")
print(f"Errors: {data['error_count']}")
print(f"Near pass count: {len(data.get('near_pass_summary', []))}")

if data.get('near_pass_summary'):
    print("\nTop near-pass candidates:")
    for np in data['near_pass_summary'][:3]:
        print(f"  - {np['field_id']}:{np['template_name']} score={np['score']:.3f}")
