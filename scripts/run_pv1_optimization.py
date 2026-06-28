"""
PV1 optimization runner based on feedback analysis

This script reads the previous test results and runs an optimized exploration
with templates specifically designed for price-volume data.
"""

import subprocess
import sys
import json
from pathlib import Path

def main():
    # Analyze previous results
    results_path = Path("results/pv1/test_results_analysis.json")
    
    if not results_path.exists():
        print("❌ No previous results found. Run initial exploration first:")
        print("   python -m alpha --dataset-id pv1 --limit 5 --max-templates-per-field 3")
        sys.exit(1)
    
    with open(results_path) as f:
        analysis = json.load(f)
    
    print("=" * 80)
    print("PV1 OPTIMIZATION ANALYSIS")
    print("=" * 80)
    print(f"\n📊 Previous Run Summary:")
    print(f"   Tested: {analysis['tested']}")
    print(f"   Submittable: {analysis['submittable_count']}")
    print(f"   Errors: {analysis['error_count']}")
    
    print(f"\n⚠️  Top Failure Reasons:")
    for check in analysis['failed_check_leaderboard']:
        print(f"   - {check['name']}: {check['count']} failures (avg value: {check['avg_value']:.2f}, need: {check['avg_limit']:.2f})")
    
    print(f"\n🎯 Optimization Strategy:")
    print(f"   1. Use pv1-specific templates with higher Sharpe focus")
    print(f"   2. Add zscore and volatility-normalized expressions")
    print(f"   3. Include mean-reversion patterns")
    print(f"   4. Use shorter time windows for price-volume data")
    print(f"   5. Skip GROUP fields (country) - incompatible with ts_backfill")
    
    print(f"\n🚀 Starting optimized run...")
    print(f"   Dataset: pv1")
    print(f"   Fields: 5 (excluding country)")
    print(f"   Templates: 14 MATRIX + 4 GROUP")
    print(f"   Template Library: data/worldquant_template_library_pv1.json")
    print()
    
    # Run optimized exploration
    cmd = [
        sys.executable, "-m", "alpha",
        "--dataset-id", "pv1",
        "--limit", "5",
        "--template-library-file", "data/worldquant_template_library_pv1.json",
        "--max-templates-per-field", "15",
    ]
    
    print(f"Command: {' '.join(cmd)}\n")
    print("=" * 80)
    
    # Execute the command
    result = subprocess.run(cmd)
    
    print("\n" + "=" * 80)
    print(f"✅ Optimized run completed with exit code: {result.returncode}")
    print("=" * 80)

if __name__ == "__main__":
    main()
