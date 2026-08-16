#!/usr/bin/env bash
#
# Deploy the Freshet licence service to Cloud Run.
#
# THIS CREATES BILLABLE RESOURCES. Read it before running it. It is written to
# be run by a person who is watching, not from CI, and it stops at every point
# where a decision is yours rather than mine.
#
#   ./deploy.sh
#
# Prerequisites you must do yourself, because they involve credentials, terms
# of service, or spend:
#
#   gcloud auth login                       # as selva@freshettax.ca
#   gcloud config set project <PROJECT_ID>
#   ...and billing enabled on that project.

set -euo pipefail

PROJECT="${PROJECT:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${REGION:-northamerica-northeast1}"   # Montréal: Canadian data residency
SERVICE="${SERVICE:-freshet-site}"
DB_INSTANCE="${DB_INSTANCE:-freshet-db}"
DOMAIN="${DOMAIN:-freshettax.ca}"

if [[ -z "$PROJECT" ]]; then
  echo "No project set. Run: gcloud config set project <PROJECT_ID>" >&2
  exit 1
fi

echo "Project : $PROJECT"
echo "Region  : $REGION   (Canadian region — customer records stay in Canada)"
echo "Service : $SERVICE"
echo
read -r -p "Deploy to this project? [y/N] " reply
[[ "$reply" == "y" || "$reply" == "Y" ]] || exit 1

# --- APIs ------------------------------------------------------------------

gcloud services enable \
  run.googleapis.com \
  sqladmin.googleapis.com \
  secretmanager.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  iap.googleapis.com \
  compute.googleapis.com

# --- The signing key -------------------------------------------------------
#
# Created by `cargo run --bin keygen`, not here. Generating a signing key
# inside a deploy script would mean a redeploy could silently mint a new one
# and invalidate every licence already sold.

if ! gcloud secrets describe freshet-signing-key >/dev/null 2>&1; then
  cat >&2 <<'EOF'
No signing key in Secret Manager.

  cd site
  cargo run --bin keygen -- ~/freshet-signing-key.hex
  gcloud secrets create freshet-signing-key --data-file=$HOME/freshet-signing-key.hex
  rm ~/freshet-signing-key.hex

Then paste the printed public key into crates/freshet-license/src/sign.rs and
rebuild the desktop app. The service refuses to start until they match.
EOF
  exit 1
fi

# --- Database --------------------------------------------------------------

if ! gcloud sql instances describe "$DB_INSTANCE" >/dev/null 2>&1; then
  echo "Creating Cloud SQL instance (this bills hourly from now on)…"
  read -r -p "Continue? [y/N] " reply
  [[ "$reply" == "y" || "$reply" == "Y" ]] || exit 1

  gcloud sql instances create "$DB_INSTANCE" \
    --database-version=POSTGRES_16 \
    --tier=db-f1-micro \
    --region="$REGION" \
    --storage-auto-increase \
    --backup-start-time=07:00

  gcloud sql databases create freshet --instance="$DB_INSTANCE"

  echo
  echo "Now create the database user yourself — a password typed by a script"
  echo "is a password in your shell history:"
  echo
  echo "  gcloud sql users set-password postgres --instance=$DB_INSTANCE --prompt-for-password"
  echo
  echo "then store the connection string:"
  echo
  echo "  gcloud secrets create freshet-database-url --data-file=-"
  echo "  # paste: postgresql://postgres:<password>@localhost/freshet?host=/cloudsql/$PROJECT:$REGION:$DB_INSTANCE"
  exit 0
fi

# --- Build and deploy ------------------------------------------------------

IMAGE="$REGION-docker.pkg.dev/$PROJECT/freshet/site:$(date +%Y%m%d-%H%M%S)"

gcloud artifacts repositories describe freshet --location="$REGION" >/dev/null 2>&1 \
  || gcloud artifacts repositories create freshet \
       --repository-format=docker --location="$REGION"

# Context is the repo root so the licence crate comes along.
gcloud builds submit .. --config=- <<EOF
steps:
  - name: gcr.io/cloud-builders/docker
    args: ['build', '-f', 'site/Dockerfile', '-t', '$IMAGE', '.']
images: ['$IMAGE']
EOF

# Ingress is restricted to the load balancer. This is not a hardening extra:
# the admin pages trust an IAP header, and a header is only trustworthy if
# nothing can reach the service without passing through IAP first.
gcloud run deploy "$SERVICE" \
  --image="$IMAGE" \
  --region="$REGION" \
  --platform=managed \
  --ingress=internal-and-cloud-load-balancing \
  --no-allow-unauthenticated \
  --add-cloudsql-instances="$PROJECT:$REGION:$DB_INSTANCE" \
  --set-secrets="FRESHET_SIGNING_KEY=freshet-signing-key:latest,DATABASE_URL=freshet-database-url:latest" \
  --set-env-vars="PUBLIC_URL=https://$DOMAIN,ADMIN_EMAILS=selva@$DOMAIN" \
  --min-instances=0 \
  --max-instances=4

cat <<EOF

Deployed.

Still to do, by you:

  1. Load balancer + managed certificate + IAP  — see docs/DEPLOY.md
  2. Point DNS at the load balancer IP          — see docs/DEPLOY.md
  3. Stripe webhook secret:
       gcloud secrets create freshet-stripe-webhook --data-file=-
       gcloud run services update $SERVICE --region=$REGION \\
         --set-secrets=STRIPE_WEBHOOK_SECRET=freshet-stripe-webhook:latest
  4. SMTP credentials for licence delivery. Until these are set the service
     LOGS licences instead of sending them, and says so on startup.
EOF
