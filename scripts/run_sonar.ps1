$ErrorActionPreference = 'Stop'
if (-not (Get-Command java -ErrorAction SilentlyContinue)) {
  $scoopJava = Join-Path $env:USERPROFILE 'scoop\apps\openjdk17\current'
  if (Test-Path $scoopJava) {
    $env:JAVA_HOME = $scoopJava
    $env:PATH = "$env:JAVA_HOME\bin;$env:PATH"
  }
}
if (Test-Path .env) {
    Get-Content .env | ForEach-Object {
      $line = $_.Trim()
      if ($line -and -not $line.StartsWith('#')) {
        $parts = $line -split '=', 2
        if ($parts.Count -eq 2) {
          $key = $parts[0].Trim()
          $val = $parts[1].Trim().Trim('"')
          [Environment]::SetEnvironmentVariable($key, $val, 'Process')
        }
      }
    }
}
if (-not $env:SONAR_HOST_URL -and $env:sonar_host_url) { $env:SONAR_HOST_URL = $env:sonar_host_url }
if (-not $env:SONAR_TOKEN -and $env:sonar_token) { $env:SONAR_TOKEN = $env:sonar_token }
if (-not $env:SONAR_HOST_URL) { throw 'SONAR_HOST_URL missing' }
if (-not $env:SONAR_TOKEN) { throw 'SONAR_TOKEN missing' }
$branch = git rev-parse --abbrev-ref HEAD
Write-Host "Running SonarScanner on branch: $branch"
& sonar-scanner "-Dsonar.host.url=$env:SONAR_HOST_URL" "-Dsonar.token=$env:SONAR_TOKEN" "-Dsonar.branch.name=$branch"
