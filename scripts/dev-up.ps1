param(
  [switch]$Build
)

Set-Location $PSScriptRoot/..
if ($Build) {
  docker compose -f infra/docker-compose.yml up --build
} else {
  docker compose -f infra/docker-compose.yml up
}
