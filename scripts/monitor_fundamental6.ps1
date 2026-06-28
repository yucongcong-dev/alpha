# Monitor fundamental6 alpha progress every check
$resultFile = "C:\Users\14772\CodeBuddy\20260618230221\alpha\results\fundamental6\test_results.json"
$logFile = "C:\Users\14772\CodeBuddy\20260618230221\alpha\results\fundamental6\monitor.log"

$ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
try {
    if (-not (Test-Path $resultFile)) {
        $msg = "$ts | WAITING: results file not yet created"
        Add-Content -Path $logFile -Value $msg -Encoding UTF8
        exit 0
    }
    $json = Get-Content $resultFile -Raw -Encoding UTF8 | ConvertFrom-Json
    $tested = $json.tested
    $submittable = $json.submittable
    $fields = $json.unique_fields_tested
    $msg = "$ts | tested=$tested | submittable=$submittable | fields=$fields"

    if ($submittable -gt 0) {
        $passes = $json.results | Where-Object { $_.submittable -eq $true }
        foreach ($p in $passes) {
            $msg += "`n  >> PASS: field=$($p.field_id) template=$($p.template_name) alpha=$($p.alpha_id)"
        }
    }

    # Show latest 3 results statuses
    $latest = $json.results | Select-Object -Last 3
    foreach ($r in $latest) {
        $statusSymbol = if ($r.submittable) { "[PASS]" } else { "[FAIL]" }
        $msg += "`n  $statusSymbol $($r.field_id) | $($r.template_name)"
    }

    Add-Content -Path $logFile -Value $msg -Encoding UTF8
} catch {
    Add-Content -Path $logFile -Value "$ts | ERROR: $_" -Encoding UTF8
}
