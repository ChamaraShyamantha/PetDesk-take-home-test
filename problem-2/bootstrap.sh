#!/usr/bin/env bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
export PATH="$PATH:/snap/bin"
DD_API_KEY_PARAM="${DD_API_KEY_PARAM:-/datadog/api_key}"
DD_SITE="${DD_SITE:-datadoghq.com}"
APT=(apt-get -y -q -o DPkg::Lock::Timeout=600)

log() { echo "$(date -u +%FT%TZ) $*"; }

exec 9>/run/bootstrap.lock
flock -n 9 || { log "Another run is in progress"; exit 1; }

report() {
  local rc=$?
  aws cloudwatch put-metric-data --namespace Bootstrap \
    --metric-name BootstrapFailed --value "$(( rc == 0 ? 0 : 1 ))" || true
  log "Finished with exit code $rc"
}
trap report EXIT

TOKEN=$(curl -fsS -X PUT "http://169.254.169.254/latest/api/token" \
  -H "X-aws-ec2-metadata-token-ttl-seconds: 300")
AWS_DEFAULT_REGION=$(curl -fsS -H "X-aws-ec2-metadata-token: $TOKEN" \
  "http://169.254.169.254/latest/meta-data/placement/region")
export AWS_DEFAULT_REGION

if ! command -v aws >/dev/null; then
  log "Installing AWS CLI"
  snap wait system seed.loaded
  snap install aws-cli --classic
fi

if ! command -v java >/dev/null; then
  "${APT[@]}" update
  JDK=$(apt-cache pkgnames openjdk- \
    | sed -nE 's/^openjdk-([0-9]+)-jdk-headless$/\1/p' \
    | awk '$1 == 8 || $1 == 11 || ($1 >= 17 && ($1 - 17) % 4 == 0)' \
    | sort -n | tail -n 1)
  log "Installing openjdk-${JDK}-jdk-headless"
  "${APT[@]}" install "openjdk-${JDK}-jdk-headless"
fi

if ! dpkg -s unattended-upgrades >/dev/null 2>&1; then
  "${APT[@]}" install unattended-upgrades
fi
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'CONF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
CONF
systemctl enable --now apt-daily.timer apt-daily-upgrade.timer

if ! dpkg -s datadog-agent >/dev/null 2>&1; then
  log "Reading Datadog API key from SSM parameter $DD_API_KEY_PARAM"
  if ! DD_KEY=$(aws ssm get-parameter --name "$DD_API_KEY_PARAM" \
      --with-decryption --query Parameter.Value --output text); then
    log "Cannot read $DD_API_KEY_PARAM. Check the instance role, region and KMS key."
    exit 1
  fi
  if [[ -z "$DD_KEY" || "$DD_KEY" == "None" ]]; then
    log "SSM parameter $DD_API_KEY_PARAM is empty"
    exit 1
  fi

  log "Installing Datadog Agent"
  curl -fsSL -o /tmp/dd-install.sh \
    https://install.datadoghq.com/scripts/install_script_agent7.sh
  DD_API_KEY="$DD_KEY" DD_SITE="$DD_SITE" DD_INSTALL_ONLY=true \
    bash /tmp/dd-install.sh
  rm -f /tmp/dd-install.sh
  unset DD_KEY
fi

mkdir -p /etc/systemd/system/datadog-agent.service.d
cat > /etc/systemd/system/datadog-agent.service.d/imdsv2.conf <<'CONF'
[Service]
Environment=DD_EC2_PREFER_IMDSV2=true
CONF
systemctl daemon-reload
systemctl enable --now datadog-agent

log "Bootstrap complete"