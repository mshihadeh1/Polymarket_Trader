$env:USE_MOCK_POLYMARKET = "false"
$env:USE_MOCK_POLYMARKET_CLIENT = "false"
$env:PAPER_TRADING_LOOP_ENABLED = "false"

Write-Host "Starting stack for real Polymarket observation mode..."
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

Write-Host "System health:"
Invoke-RestMethod http://localhost:8000/api/v1/system/health | ConvertTo-Json -Depth 8

Write-Host "Recent markets:"
Invoke-RestMethod "http://localhost:8000/api/v1/markets?short_horizon_only=true" | ConvertTo-Json -Depth 8

Write-Host "Tail API logs with:"
Write-Host "  docker compose --env-file .env -f infrastructure/docker-compose.yml logs -f api"
Write-Host "Open http://localhost:3000 and use the BTC quick-launch cards to inspect a live market."
