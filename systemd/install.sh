#!/usr/bin/env bash
# Install WhisperWriter as systemd --user services that start on login/boot.
#
# Which services get installed is driven by config:
#   1. command-line args:   ./install.sh server client
#   2. else install.conf:   WW_SERVICES="server client"
#
# Roles -> unit files:
#   direct  -> whisper-writer-local.service         (GUI client, loads model in-process)
#   server  -> whisper-writer-server.service        (transcription server on :47892)
#   client  -> whisper-writer-client-local.service  (GUI client using the local server)
#   remote  -> whisper-writer-remote.service         (GUI client -> gratitude via SSH tunnel)
#
# Re-running is safe: it re-syncs whatever WW_SERVICES says and stops/disables
# any WhisperWriter unit no longer selected.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USER_UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"

# --- resolve which roles to install ------------------------------------------
if [[ $# -gt 0 ]]; then
    ROLES="$*"
elif [[ -f "$SCRIPT_DIR/install.conf" ]]; then
    # shellcheck disable=SC1091
    source "$SCRIPT_DIR/install.conf"
    ROLES="${WW_SERVICES:-}"
fi

if [[ -z "${ROLES// }" ]]; then
    echo "No services selected. Pass roles as args or set WW_SERVICES in install.conf." >&2
    echo "Roles: direct | server | client | remote" >&2
    exit 1
fi

# --- map roles -> unit files -------------------------------------------------
declare -A ROLE_UNIT=(
    [direct]=whisper-writer-local.service
    [server]=whisper-writer-server.service
    [client]=whisper-writer-client-local.service
    [remote]=whisper-writer-remote.service
)
ALL_UNITS=(
    whisper-writer-local.service
    whisper-writer-server.service
    whisper-writer-client-local.service
    whisper-writer-remote.service
)

WANT_UNITS=()
want_server=0
want_client=0
for role in $ROLES; do
    unit="${ROLE_UNIT[$role]:-}"
    if [[ -z "$unit" ]]; then
        echo "Unknown role: '$role' (valid: ${!ROLE_UNIT[*]})" >&2
        exit 1
    fi
    WANT_UNITS+=("$unit")
    [[ "$role" == server ]] && want_server=1
    [[ "$role" == client ]] && want_client=1
done

if [[ $want_client -eq 1 && $want_server -eq 0 ]]; then
    echo "Role 'client' needs a local 'server' to talk to — add 'server' to WW_SERVICES." >&2
    exit 1
fi

echo "Installing: ${WANT_UNITS[*]}"
mkdir -p "$USER_UNIT_DIR"

# --- disable any WhisperWriter unit we are NOT installing ---------------------
is_wanted() { local u; for u in "${WANT_UNITS[@]}"; do [[ "$u" == "$1" ]] && return 0; done; return 1; }
for unit in "${ALL_UNITS[@]}"; do
    if ! is_wanted "$unit" && [[ -f "$USER_UNIT_DIR/$unit" ]]; then
        echo "Removing stale unit: $unit"
        systemctl --user disable --now "$unit" 2>/dev/null || true
        rm -f "$USER_UNIT_DIR/$unit"
    fi
done

# --- install selected units --------------------------------------------------
for unit in "${WANT_UNITS[@]}"; do
    cp "$SCRIPT_DIR/$unit" "$USER_UNIT_DIR/$unit"
done

systemctl --user daemon-reload
for unit in "${WANT_UNITS[@]}"; do
    systemctl --user enable --now "$unit"
done

# --- linger so the server survives logout / starts at boot -------------------
if [[ $want_server -eq 1 ]]; then
    if [[ "$(loginctl show-user "$USER" -p Linger --value 2>/dev/null)" != "yes" ]]; then
        echo "Enabling linger so services start at boot without login (needs sudo)..."
        sudo loginctl enable-linger "$USER" || \
            echo "Could not enable linger; run: sudo loginctl enable-linger $USER" >&2
    fi
fi

echo
echo "Done. Status:"
for unit in "${WANT_UNITS[@]}"; do
    printf '  %-38s %s\n' "$unit" "$(systemctl --user is-active "$unit" 2>/dev/null || echo inactive)"
done
echo
echo "Logs:   journalctl --user -u <unit> -f"
