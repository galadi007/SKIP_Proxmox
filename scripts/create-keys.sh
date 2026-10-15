#!/usr/bin/env bash
set -euo pipefail

success() { printf '\033[32m[SUCCESS] %s\033[0m\n' "$*"; }
error() { printf '\033[31m[ERROR] %s\033[0m\n' "$*" >&2; }
info() { printf '\033[34m[INFO] %s\033[0m\n' "$*"; }

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
KEYS_DIR="$ROOT_DIR/keys"
PRIVATE_KEY="$KEYS_DIR/argocd-github-key"
PUBLIC_KEY="$PRIVATE_KEY.pub"

if ! command -v ssh-keygen >/dev/null 2>&1; then
  error "ssh-keygen nicht gefunden. Programm wird beendet"
  exit 1
fi
success "ssh-keygen gefunden!"

info "Erstelle Ordner $KEYS_DIR ..."
if ! mkdir -p -- "$KEYS_DIR"; then
  error "Fehler beim Erstellen des Ordners $KEYS_DIR. Programm wird abgebrochen."
  exit 1
fi
success "Ordner $KEYS_DIR erstellt"

if [[ -e "$PRIVATE_KEY" && -e "$PUBLIC_KEY" ]]; then
  info "SSH-Schlüssel existieren bereits. Überspringe Generierung."
  exit 0
fi

if [[ -e "$PRIVATE_KEY" || -e "$PUBLIC_KEY" ]]; then
  error "SSH-Schlüsselpaar ist unvollständig. Ausführung wird abgebrochen."
  exit 1
fi

info "Generiere SSH-Schlüssel..."
if ! ssh-keygen -t ed25519 -C argocd-github -f "$PRIVATE_KEY" -N "" </dev/null >/dev/null; then
  error "Fehler beim Generieren der Schlüssel."
  exit 1
fi
success "SSH-Schlüssel erfolgreich generiert."
