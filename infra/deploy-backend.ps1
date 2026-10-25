param(
    [string]$ProjectId = 'optimapper-489016',
    [string]$Region = 'europe-west1',
    [string]$Service = 'optimapper-api',
    [string]$FrontendOrigin = 'https://optimapper.vercel.app',
    [string]$Gcloud = 'gcloud',
    [string]$Tag = 'candidate'
)

$ErrorActionPreference = 'Stop'
$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$commit = (git -c "safe.directory=$repoRoot" -C $repoRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Could not identify the source commit.' }
$dirty = git -c "safe.directory=$repoRoot" -C $repoRoot status --porcelain --untracked-files=normal
if ($LASTEXITCODE -ne 0 -or $dirty) { throw 'Commit source changes before deploying.' }
$image = "$Region-docker.pkg.dev/$ProjectId/cloud-run-source-deploy/${Service}:$commit"

# Explicit e2-medium build workers; avoid larger paid build machine types.
& $Gcloud builds submit (Join-Path $repoRoot 'backend') --project=$ProjectId --region=$Region --tag=$image --machine-type=e2-medium --timeout=600 --suppress-logs --quiet
if ($LASTEXITCODE -ne 0) { throw 'Container build failed. The current service was not changed.' }

$deployArgs = @(
    'run', 'deploy', $Service,
    "--project=$ProjectId", "--region=$Region", "--image=$image",
    '--no-traffic', "--tag=$Tag",
    '--cpu=1', '--memory=512Mi', '--concurrency=2', '--timeout=300',
    '--cpu-throttling', '--cpu-boost',
    '--min=0', '--max=1', '--min-instances=0', '--max-instances=1',
    "--update-env-vars=ALLOWED_ORIGINS=$FrontendOrigin,GOOGLE_ROUTES_MAX_ELEMENTS=100,ENABLE_AI_SUGGESTIONS=false",
    '--update-secrets=GOOGLE_MAPS_API_KEY=optimapper-google-maps-key:1',
    "--update-labels=commit-sha=$commit,source-branch=feat-time-aware-itineraries",
    '--quiet'
)
& $Gcloud @deployArgs
if ($LASTEXITCODE -ne 0) { throw 'Candidate deployment failed. Check the Cloud Run revision logs.' }

Write-Output 'Candidate deployed without production traffic. Verify it and deploy the matching frontend before promoting it.'
& $Gcloud run services describe $Service --region=$Region --project=$ProjectId '--format=json(status.latestReadyRevisionName,status.traffic)'
