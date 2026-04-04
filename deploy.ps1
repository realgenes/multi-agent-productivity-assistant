param(
    [string]$ProjectId,
    [string]$Region = "us-central1",
    [string]$ServiceName = "multi-agent-productivity-assistant",
    [string]$ImageName = "multi-agent-assistant/app",
    [string]$Model = "gemini-2.5-flash",
    [string]$RuntimeServiceAccount
)

if (-not $ProjectId) {
    throw "ProjectId is required."
}

$runtimeServiceAccount = $RuntimeServiceAccount
if (-not $runtimeServiceAccount) {
    $runtimeServiceAccount = "multi-agent-run@$ProjectId.iam.gserviceaccount.com"
}

$image = "$Region-docker.pkg.dev/$ProjectId/$ImageName`:latest"

gcloud builds submit `
  --project $ProjectId `
  --config cloudbuild.yaml `
  --substitutions "_SERVICE_NAME=$ServiceName,_REGION=$Region,_IMAGE=$image,_MODEL=$Model,_USE_VERTEX_AI=true,_RUNTIME_SERVICE_ACCOUNT=$runtimeServiceAccount"
