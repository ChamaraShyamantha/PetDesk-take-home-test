#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
APP="${PROBLEM4_DIR:-$HERE/../problem-4}"
GITOPS="$HOME/Documents/PetDesk-Problem5-GitOps"
TAG="$(git -C "$APP" rev-parse --short HEAD)"

echo "==> Cluster and Gateway"
k3d cluster create --config "$HERE/k3d/cluster.yaml"
kubectl apply -f "$HERE/platform/traefik-gateway.yaml"
until kubectl get gatewayclass traefik >/dev/null 2>&1; do sleep 5; done
kubectl apply -f "$HERE/platform/gateway.yaml"

echo "==> Image demo-app:$TAG"
docker build -q -t "demo-app:$TAG" "$APP"
k3d image import "demo-app:$TAG" -c petdesk

echo "==> Gitea and Argo CD"
kubectl apply -f "$HERE/platform/gitea.yaml"
kubectl create namespace argocd
kubectl apply -n argocd --server-side \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/v3.5.5/manifests/install.yaml
kubectl -n argocd patch configmap argocd-cmd-params-cm -p '{"data":{"server.insecure":"true"}}'
kubectl -n argocd rollout restart deploy/argocd-server
kubectl -n gitea rollout status deploy/gitea --timeout=300s
kubectl -n argocd rollout status deploy/argocd-repo-server --timeout=300s

echo "==> Push the chart to Gitea"
PW="$(openssl rand -hex 12)"
kubectl -n gitea exec deploy/gitea -- gitea admin user create --admin --username petdesk \
  --password "$PW" --email petdesk@example.local --must-change-password=false
kubectl -n gitea port-forward svc/gitea-http 3001:3000 >/dev/null 2>&1 &
trap "kill $! 2>/dev/null || true" EXIT
sleep 3
curl -fsS -u "petdesk:$PW" -H 'Content-Type: application/json' \
  -d '{"name":"demo-gitops","default_branch":"main"}' \
  http://localhost:3001/api/v1/user/repos >/dev/null

mkdir -p "$GITOPS" && rm -rf "$GITOPS/.git" "$GITOPS/problem-5"
echo "$PW" > "$GITOPS/.gitea-password"
printf "%s\n" .gitea-password "argocd-deploy-key*" > "$GITOPS/.gitignore"
cp -R "$HERE" "$GITOPS/problem-5"
sed -i '' "s/tag: \".*\"/tag: \"$TAG\"/" "$GITOPS/problem-5/chart/demo-app/values.yaml"
git -C "$GITOPS" init -q -b main
git -C "$GITOPS" add -A
git -C "$GITOPS" commit -qm "Deploy demo-app $TAG"
git -C "$GITOPS" push -q "http://petdesk:$PW@localhost:3001/petdesk/demo-gitops.git" main

echo "==> Argo CD Application"
kubectl apply -f "$HERE/argocd/application.yaml"
until [ "$(kubectl -n argocd get app demo-app -o jsonpath='{.status.sync.status}/{.status.health.status}' 2>/dev/null)" = "Synced/Healthy" ]; do
  sleep 5
done

echo "==> Done: curl localhost:8088"
