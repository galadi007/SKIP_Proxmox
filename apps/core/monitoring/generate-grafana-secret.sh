#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
output_file="${script_dir}/grafana-admin-sealedsecret.yaml"

for required_command in kubectl kubeseal; do
  if ! command -v "${required_command}" >/dev/null 2>&1; then
    printf 'Fehler: %s ist nicht installiert oder nicht im PATH.\n' "${required_command}" >&2
    exit 1
  fi
done

printf 'Grafana-Administrator [admin]: '
read -r grafana_admin
grafana_admin="${grafana_admin:-admin}"

printf 'Grafana-Passwort (mindestens 16 Zeichen): '
read -r -s grafana_password
printf '\n'

printf 'Grafana-Passwort wiederholen: '
read -r -s grafana_password_repeat
printf '\n'

if [[ "${grafana_password}" != "${grafana_password_repeat}" ]]; then
  printf 'Fehler: Die Passwoerter stimmen nicht ueberein.\n' >&2
  exit 1
fi

if (( ${#grafana_password} < 16 )); then
  printf 'Fehler: Das Passwort muss mindestens 16 Zeichen lang sein.\n' >&2
  exit 1
fi

temporary_file="$(mktemp "${output_file}.tmp.XXXXXX")"
cleanup() {
  unset grafana_password grafana_password_repeat
  if [[ -f "${temporary_file}" ]]; then
    rm -f -- "${temporary_file}"
  fi
}
trap cleanup EXIT

# Das Klartext-Secret wird nur im Speicher erzeugt und direkt an kubeseal
# weitergereicht. Es wird zu keinem Zeitpunkt auf die Festplatte geschrieben.
printf 'admin-user=%s\nadmin-password=%s\n' \
  "${grafana_admin}" "${grafana_password}" |
  kubectl --namespace monitoring create secret generic grafana-admin-credentials \
    --from-env-file=/dev/stdin \
    --dry-run=client \
    --output=yaml |
  kubeseal \
    --controller-name sealed-secrets \
    --controller-namespace sealed-secrets \
    --format yaml >"${temporary_file}"

if ! grep -q '^kind: SealedSecret$' "${temporary_file}"; then
  printf 'Fehler: kubeseal hat kein gueltiges SealedSecret erzeugt.\n' >&2
  exit 1
fi

chmod 0644 "${temporary_file}"
mv -- "${temporary_file}" "${output_file}"
unset grafana_password grafana_password_repeat

printf 'Erzeugt: %s\n' "${output_file}"
printf 'Diese verschluesselte YAML-Datei darf in Git committed werden.\n'
