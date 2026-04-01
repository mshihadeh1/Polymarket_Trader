$limit = if ($args.Count -ge 1) { $args[0] } else { "10" }
$asset = if ($args.Count -ge 2) { $args[1] } else { "BTC" }
$timeframe = if ($args.Count -ge 3) { $args[2] } else { "crypto_5m" }

$env:EXTERNAL_HISTORICAL_PROVIDER = "csv"
$env:USE_MOCK_EXTERNAL_PROVIDER = "false"
$env:PAPER_TRADING_LOOP_ENABLED = "false"

Write-Host "Starting stack for CSV baseline backtest..."
docker compose --env-file .env -f infrastructure/docker-compose.yml up -d --build

Write-Host "Waiting for API health..."
for ($i = 0; $i -lt 60; $i++) {
    try {
        Invoke-RestMethod http://localhost:8000/healthz | Out-Null
        break
    }
    catch {
        Start-Sleep -Seconds 2
    }

    if ($i -eq 59) {
        throw "API did not become healthy within 120 seconds."
    }
}

Write-Host "CSV validation report:"
Invoke-RestMethod http://localhost:8000/api/v1/external-provider | ConvertTo-Json -Depth 8

Write-Host "Eligible closed markets:"
Invoke-RestMethod "http://localhost:8000/api/v1/evaluations/closed-markets?asset=$asset&timeframe=$timeframe&limit=$limit" | ConvertTo-Json -Depth 8

Write-Host "Running baseline closed-market batch without Hyperliquid enrichment..."
Invoke-RestMethod -Method Post "http://localhost:8000/api/v1/evaluations/closed-markets/run?asset=$asset&timeframe=$timeframe&limit=$limit&strategy_name=combined_cvd_gap&include_hyperliquid_enrichment=false" | ConvertTo-Json -Depth 8

Write-Host "Open http://localhost:3000/backtests?asset=$asset&timeframe=$timeframe&limit=$limit to inspect the results."
