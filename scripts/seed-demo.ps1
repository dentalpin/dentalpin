# Seed DentalPin with demo data in PowerShell
# Usage: .\scripts\seed-demo.ps1 [-Lang en|es|ar]
param(
    [string]$Lang = ""
)

Write-Host "Seeding demo data..."
if ($Lang) {
    docker compose exec -T -e PYTHONPATH=/app backend python scripts/seed_demo.py --lang $Lang
} else {
    docker compose exec -T -e PYTHONPATH=/app backend python scripts/seed_demo.py
}
