#!/usr/bin/env bash
set -Eeuo pipefail

JARVIS_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_PYTHON="${JARVIS_RUNTIME_PYTHON:-/home/alex/jarvis-venv/bin/python3}"
PROC_ROOT="${JARVIS_PROC_ROOT:-/proc}"
[[ -x "$RUNTIME_PYTHON" ]] || { echo "ERROR: JARVIS Python-Runtime fehlt."; exit 1; }
llm_port="$(cd "$JARVIS_ROOT" && "$RUNTIME_PYTHON" scripts/check_runtime_dependencies.py --llm-port)"
STATE_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/jarvis-runtime"
mkdir -p "$STATE_DIR"
exec 9>"$STATE_DIR/control.lock"
if ! flock -w 300 9; then
    echo "ERROR: Ein anderer JARVIS-Lifecycle-Vorgang hat den Lock nicht rechtzeitig freigegeben."
    exit 1
fi

started_llm=0
started_chatterbox=0
started_jarvis=0
degraded=0
state=STARTING
echo "$state"

fail() {
    code=$?
    trap - ERR
    if (( started_jarvis )); then systemctl --user stop jarvis.service >/dev/null 2>&1 || true; fi
    if (( started_chatterbox == 1 )); then systemctl --user stop jarvis-chatterbox.service >/dev/null 2>&1 || true; fi
    if (( started_chatterbox == 2 )); then sudo -n systemctl stop chatterbox.service >/dev/null 2>&1 || true; fi
    if (( started_llm )); then systemctl --user stop llama-server.service >/dev/null 2>&1 || true; fi
    echo "ERROR: Start fehlgeschlagen (exit $code); neu gestartete JARVIS-Dienste wurden bereinigt."
    exit "$code"
}
trap fail ERR

unit_field() { systemctl --user show "$1" --property="$2" --value 2>/dev/null || true; }
require_matching_llm_unit() {
    local state fragment execstart pid owner llm_exe
    state="$(unit_field llama-server.service LoadState)"
    fragment="$(unit_field llama-server.service FragmentPath)"
    execstart="$(unit_field llama-server.service ExecStart)"
    [[ "$state" == loaded && "$fragment" == /home/alex/.config/systemd/user/llama-server.service ]] || {
        echo "LLM-User-Unit fehlt oder ist nicht die bestätigte Sleepy-Unit."
        return 1
    }
    [[ "$execstart" == *"/home/alex/llama.cpp/build/bin/llama-server"* \
        && ( "$execstart" == *"--host 127.0.0.1"* || "$execstart" == *"--host=127.0.0.1"* ) \
        && ( "$execstart" == *"--port $llm_port"* || "$execstart" == *"--port=$llm_port"* ) ]] || {
        echo "LLM-Unit entspricht nicht der bestätigten Binary, Loopback-Adresse und Config-Port."
        return 1
    }
    pid="$(unit_field llama-server.service MainPID)"
    sockets="$(ss -ltnp "sport = :$llm_port" 2>/dev/null || true)"
    listening="$(sed -n '2,$p' <<<"$sockets")"
    owner="$(sed -n 's/.*pid=\([0-9][0-9]*\).*/\1/p' <<<"$sockets" | sort -u)"
    if [[ -n "$listening" && -z "$owner" ]]; then
        echo "Konfigurierter LLM-Port ist belegt, der Prozessbesitzer kann aber nicht sicher gelesen werden."
        return 1
    fi
    if [[ -n "$owner" ]]; then
        [[ "$(unit_field llama-server.service ActiveState)" == active && "$owner" == "$pid" ]] || {
            echo "Konfigurierter LLM-Port ist durch einen nicht zugeordneten Prozess belegt (PID $owner)."
            return 1
        }
        llm_exe="$(readlink -f "$PROC_ROOT/$pid/exe" 2>/dev/null || true)"
        [[ "$llm_exe" == /home/alex/llama.cpp/build/bin/llama-server ]] || {
            echo "Der LLM-Service-Prozess stimmt nicht mit der bestätigten Binary überein."
            return 1
        }
    elif [[ "$(unit_field llama-server.service ActiveState)" == active ]]; then
        [[ "$pid" =~ ^[1-9][0-9]*$ ]] || {
            echo "LLM-Unit ist aktiv, meldet aber keinen laufenden Prozess."
            return 1
        }
        llm_exe="$(readlink -f "$PROC_ROOT/$pid/exe" 2>/dev/null || true)"
        [[ "$llm_exe" == /home/alex/llama.cpp/build/bin/llama-server ]] || {
            echo "LLM-Unit ist aktiv, aber ihr Prozess entspricht nicht dem erwarteten llama-server."
            return 1
        }
    fi
}

require_loopback_llm_listener() {
    local sockets
    sockets="$(ss -ltnp "sport = :$llm_port" 2>/dev/null || true)"
    awk -v port="$llm_port" '
        NR > 1 {
            address = $4
            if (address != "127.0.0.1:" port && address != "[::1]:" port) bad = 1
            found = 1
        }
        END { exit (!found || bad) }
    ' <<<"$sockets" || {
        echo "LLM-Port $llm_port lauscht nicht ausschließlich auf einer Loopback-Adresse."
        return 1
    }
}

require_matching_llm_unit
if [[ "$(unit_field llama-server.service ActiveState)" != active ]]; then
    started_llm=1
    systemctl --user start llama-server.service
fi
llm_ready=0
for _ in {1..180}; do
    if [[ "$(unit_field llama-server.service ActiveState)" == active ]]; then
        llm_pid="$(unit_field llama-server.service MainPID)"
        [[ "$llm_pid" =~ ^[1-9][0-9]*$ ]] || {
            echo "LLM-Unit ist aktiv, meldet aber keinen laufenden Prozess."
            false
        }
        [[ "$(readlink -f "$PROC_ROOT/$llm_pid/exe" 2>/dev/null || true)" == /home/alex/llama.cpp/build/bin/llama-server ]] || {
            echo "LLM-Service-Prozess stimmt nicht mit der bestätigten Binary überein."
            false
        }
        llm_sockets="$(ss -ltnp "sport = :$llm_port" 2>/dev/null || true)"
        llm_listening="$(sed -n '2,$p' <<<"$llm_sockets")"
        llm_owner="$(sed -n 's/.*pid=\([0-9][0-9]*\).*/\1/p' <<<"$llm_sockets" | sort -u)"
        if [[ -n "$llm_listening" && -z "$llm_owner" ]]; then
            echo "Konfigurierter LLM-Port ist belegt, der Prozessbesitzer kann aber nicht sicher gelesen werden."
            false
        fi
        if [[ -n "$llm_owner" ]]; then
            [[ "$llm_owner" == "$llm_pid" ]] || {
                echo "Konfigurierter LLM-Port ist durch einen nicht zum Service gehörenden Prozess belegt (PID $llm_owner)."
                false
            }
            require_loopback_llm_listener
            if "$RUNTIME_PYTHON" "$JARVIS_ROOT/scripts/check_runtime_dependencies.py" --llm-health >/dev/null; then
                llm_ready=1
                break
            fi
        fi
    fi
    sleep 1
done
(( llm_ready )) || { echo "Lokaler LLM-Service hat innerhalb von 180 Sekunden keine Bereitschaft erreicht."; false; }

unit_field_for_scope() {
    local scope="$1" unit="$2" property="$3"
    if [[ "$scope" == user ]]; then
        systemctl --user show "$unit" --property="$property" --value 2>/dev/null || true
    else
        systemctl show "$unit" --property="$property" --value 2>/dev/null || true
    fi
}

process_in_control_group() {
    local pid="$1" expected_cgroup="$2" hierarchy controllers actual_cgroup
    [[ "$expected_cgroup" == /* && -r "$PROC_ROOT/$pid/cgroup" ]] || return 1
    while IFS=: read -r hierarchy controllers actual_cgroup; do
        if [[ "$actual_cgroup" == "$expected_cgroup" || "$actual_cgroup" == "$expected_cgroup/"* ]]; then
            return 0
        fi
    done <"$PROC_ROOT/$pid/cgroup"
    return 1
}

verify_chat_unit_owns_pid() {
    local scope="$1" unit="$2" pid="$3"
    local load active main_pid control_group fragment execstart working_directory unit_user
    load="$(unit_field_for_scope "$scope" "$unit" LoadState)"
    active="$(unit_field_for_scope "$scope" "$unit" ActiveState)"
    main_pid="$(unit_field_for_scope "$scope" "$unit" MainPID)"
    control_group="$(unit_field_for_scope "$scope" "$unit" ControlGroup)"
    fragment="$(unit_field_for_scope "$scope" "$unit" FragmentPath)"
    execstart="$(unit_field_for_scope "$scope" "$unit" ExecStart)"
    [[ "$load" == loaded && "$active" == active && "$main_pid" == "$pid" && -n "$control_group" ]] || return 1
    process_in_control_group "$pid" "$control_group" || return 1

    if [[ "$scope" == user ]]; then
        working_directory="$(unit_field_for_scope user "$unit" WorkingDirectory)"
        [[ "$unit" == jarvis-chatterbox.service \
            && "$fragment" =~ ^/run/user/[0-9]+/systemd/transient/jarvis-chatterbox\.service$ \
            && "$working_directory" == "$JARVIS_ROOT" \
            && "$execstart" == *"argv[]=/bin/bash $JARVIS_ROOT/start_chatterbox.sh"* ]] || return 1
    else
        unit_user="$(unit_field_for_scope system "$unit" User)"
        [[ "$unit" == chatterbox.service \
            && "$fragment" == /etc/systemd/system/chatterbox.service \
            && -f "$fragment" && ! -L "$fragment" \
            && "$unit_user" == alex \
            && "$execstart" == *"argv[]=/bin/bash $JARVIS_ROOT/start_chatterbox.sh"* \
            && "$execstart" != *"flags=privileged"* ]] || return 1
        local unit_owner unit_mode
        unit_owner="$(stat -c '%U:%G' "$fragment" 2>/dev/null || true)"
        unit_mode="$(stat -c '%a' "$fragment" 2>/dev/null || true)"
        [[ "$unit_owner" == root:root && "$unit_mode" =~ ^[0-7]+$ ]] || return 1
        (( (8#$unit_mode & 022) == 0 )) || return 1
    fi
}

verify_chat_owner() {
    local pid process_pid process_uid expected_uid actual_exe expected_exe
    local -a process_argv=()
    pid="$(ss -ltnp 'sport = :8765' 2>/dev/null | sed -n 's/.*pid=\([0-9][0-9]*\).*/\1/p' | sort -u)"
    [[ "$pid" =~ ^[1-9][0-9]*$ && -r "$PROC_ROOT/$pid/status" ]] || {
        echo "Port 8765 ist nicht eindeutig einem einzelnen Prozess zugeordnet."
        return 1
    }

    process_pid="$(awk '/^Pid:/{print $2; exit}' "$PROC_ROOT/$pid/status" 2>/dev/null || true)"
    process_uid="$(awk '/^Uid:/{print $2; exit}' "$PROC_ROOT/$pid/status" 2>/dev/null || true)"
    expected_uid="$(id -u alex 2>/dev/null || true)"
    mapfile -d '' -t process_argv <"$PROC_ROOT/$pid/cmdline" 2>/dev/null || true
    actual_exe="$(readlink -f "$PROC_ROOT/$pid/exe" 2>/dev/null || true)"
    expected_exe="$(readlink -f /home/alex/chatterbox-venv/bin/python3 2>/dev/null || true)"
    if [[ "${#process_argv[@]}" -ne 2 ]]; then
        echo "Port 8765 ist von einem fremden oder nicht eindeutig identifizierten Prozess belegt (PID $pid)."
        return 1
    fi
    [[ "$process_pid" == "$pid" && "$process_uid" == "$expected_uid" \
        && "$expected_uid" =~ ^[0-9]+$ \
        && "${process_argv[0]}" == /home/alex/chatterbox-venv/bin/python3 \
        && "${process_argv[1]}" == "$JARVIS_ROOT/tools/chatterbox_server.py" \
        && -n "$expected_exe" && "$actual_exe" == "$expected_exe" ]] || {
        echo "Port 8765 ist von einem fremden oder nicht eindeutig identifizierten Prozess belegt (PID $pid)."
        return 1
    }

    if ! verify_chat_unit_owns_pid user jarvis-chatterbox.service "$pid" \
        && ! verify_chat_unit_owns_pid system chatterbox.service "$pid"; then
        echo "Port 8765 ist nicht der aktiven JARVIS-Chatterbox-Unit zugeordnet (PID $pid)."
        return 1
    fi

    local current_listener_pid
    current_listener_pid="$(ss -ltnp 'sport = :8765' 2>/dev/null | sed -n 's/.*pid=\([0-9][0-9]*\).*/\1/p' | sort -u)"
    [[ "$current_listener_pid" == "$pid" ]] || {
        echo "Der Prozessbesitzer von Port 8765 hat sich während der Prüfung geändert."
        return 1
    }
}

# Reuse only the exact project Chatterbox process. An unknown port owner is
# never stopped or replaced.
chat_sockets="$(ss -ltnp 'sport = :8765' 2>/dev/null || true)"
chat_pid="$(sed -n 's/.*pid=\([0-9][0-9]*\).*/\1/p' <<<"$chat_sockets" | sort -u)"
chat_listening="$(sed -n '2,$p' <<<"$chat_sockets")"
if [[ -n "$chat_listening" && -z "$chat_pid" ]]; then
    echo "Port 8765 ist belegt, der Prozessbesitzer kann aber nicht sicher gelesen werden."
    false
fi
check_chat_runtime() {
    local output journal_output
    if output="$("$RUNTIME_PYTHON" "$JARVIS_ROOT/scripts/check_chatterbox_runtime.py" "$@" 2>&1)"; then
        return 0
    fi
    if [[ -n "${chat_journal_since:-}" ]]; then
        if [[ "${chat_journal_scope:-user}" == user ]]; then
            journal_output="$(journalctl --user -u "${chat_journal_unit:-jarvis-chatterbox.service}" --since "$chat_journal_since" --no-pager --output=cat 2>/dev/null || true)"
        else
            journal_output="$(journalctl -u "${chat_journal_unit:-chatterbox.service}" --since "$chat_journal_since" --no-pager --output=cat 2>/dev/null || true)"
        fi
    fi
    if grep -Fq 'No CUDA GPUs are available' <<<"$output$journal_output"; then
        echo "Chatterbox kann nicht starten: Die bestehende PyTorch-Runtime erkennt keine CUDA-fähige GPU."
    elif grep -Eqi 'Driver not initialized|amdgpu.*not found in modules' <<<"$output$journal_output"; then
        echo "Chatterbox kann nicht starten: Der WSL-GPU-Treiber oder GPU-Passthrough ist nicht verfügbar."
    elif grep -q '/health' <<<"$output"; then
        echo "Chatterbox Health-Endpunkt ist nicht erreichbar oder meldet einen Fehler."
    elif grep -q '/config\|Runtime-Konfiguration' <<<"$output"; then
        echo "Chatterbox Runtime weicht von der kanonischen Voice-Konfiguration ab."
    elif grep -q 'Voice-Anker\|SHA256' <<<"$output"; then
        echo "Chatterbox Voice-Anker fehlt oder sein Integritätscheck schlägt fehl."
    else
        echo "Chatterbox Runtime-Prüfung ist fehlgeschlagen (Details aus Datenschutzgründen ausgeblendet)."
    fi
    return 1
}

if [[ -n "$chat_pid" ]]; then
    verify_chat_owner
    check_chat_runtime
else
    system_state="$(systemctl show chatterbox.service --property=LoadState --value 2>/dev/null || true)"
    system_fragment="$(systemctl show chatterbox.service --property=FragmentPath --value 2>/dev/null || true)"
    system_active="$(systemctl show chatterbox.service --property=ActiveState --value 2>/dev/null || true)"
    system_user="$(systemctl show chatterbox.service --property=User --value 2>/dev/null || true)"
    system_exec="$(systemctl show chatterbox.service --property=ExecStart --value 2>/dev/null || true)"
    unit_file=/etc/systemd/system/chatterbox.service
    if [[ "$system_state" == loaded ]]; then
        chat_journal_scope=system
        chat_journal_unit=chatterbox.service
        chat_journal_since="$(date --iso-8601=seconds)"
        [[ "$system_fragment" == "$unit_file" && -f "$unit_file" && ! -L "$unit_file" ]] || {
            echo "Chatterbox-System-Unit ist nicht die erwartete reguläre Unit-Datei."
            false
        }
        unit_owner="$(stat -c '%U:%G' "$unit_file" 2>/dev/null || true)"
        unit_mode="$(stat -c '%a' "$unit_file" 2>/dev/null || true)"
        [[ "$unit_owner" == root:root && "$system_user" == alex && "$system_exec" == *"path=/bin/bash"* && "$system_exec" == *"argv[]=/bin/bash /mnt/c/Users/Alex/Projekte/JARVIS-Sleepy/Main/start_chatterbox.sh"* && "$system_exec" != *"flags=privileged"* ]] || {
            echo "Installierte Chatterbox-System-Unit ist nicht die bestätigte User-Exec-Unit."
            false
        }
        [[ "$unit_mode" =~ ^[0-7]+$ ]] && (( (8#$unit_mode & 022) == 0 )) || {
            echo "Installierte Chatterbox-System-Unit ist für Gruppe oder andere Benutzer beschreibbar."
            false
        }
        if [[ "$system_active" == active ]]; then
            echo "Chatterbox-System-Unit ist aktiv, aber Port 8765 ist nicht bereit."
            false
        fi
        sudo -n true || { echo "Die geprüfte Chatterbox-System-Unit benötigt nichtinteraktives sudo."; false; }
        started_chatterbox=2
        sudo -n systemctl start chatterbox.service
    elif [[ "$system_state" == not-found || -z "$system_state" ]]; then
        chat_journal_scope=user
        chat_journal_unit=jarvis-chatterbox.service
        chat_journal_since="$(date --iso-8601=seconds)"
        transient_state="$(unit_field jarvis-chatterbox.service LoadState)"
        if [[ "$transient_state" == loaded ]]; then
            transient_fragment="$(unit_field jarvis-chatterbox.service FragmentPath)"
            transient_exec="$(unit_field jarvis-chatterbox.service ExecStart)"
            [[ "$transient_fragment" == /run/user/*/systemd/transient/jarvis-chatterbox.service && "$transient_exec" == *"/bin/bash $JARVIS_ROOT/start_chatterbox.sh"* ]] || {
                echo "jarvis-chatterbox.service ist keine von diesem JARVIS gestartete Transient-Unit."
                false
            }
            if [[ "$(unit_field jarvis-chatterbox.service ActiveState)" != active ]]; then
                started_chatterbox=1
                systemctl --user start jarvis-chatterbox.service
            fi
        else
            started_chatterbox=1
            systemd-run --user --unit=jarvis-chatterbox --collect \
                --property="WorkingDirectory=$JARVIS_ROOT" \
                --property=Restart=on-failure \
                --property=RestartSec=10 \
                --property=TimeoutStopSec=20 \
                --property=StandardOutput=journal \
                --property=StandardError=journal \
                /bin/bash "$JARVIS_ROOT/start_chatterbox.sh"
        fi
    else
        echo "Chatterbox-System-Unit ist im Zustand '$system_state'; Start aus Sicherheitsgründen abgebrochen."
        false
    fi
    check_chat_runtime --wait 180
    verify_chat_owner
fi

# The JARVIS unit is user-scoped and points at this checkout. Link it once,
# without enabling it for automatic boot or replacing an existing unit.
jarvis_load="$(unit_field jarvis.service LoadState)"
if [[ "$jarvis_load" == not-found ]]; then
    systemctl --user link "$JARVIS_ROOT/systemd/jarvis.service"
    systemctl --user daemon-reload
    jarvis_load="$(unit_field jarvis.service LoadState)"
fi
[[ "$jarvis_load" == loaded ]] || { echo "JARVIS-User-Unit ist nicht geladen."; false; }
jarvis_fragment="$(unit_field jarvis.service FragmentPath)"
jarvis_fragment_real="$(readlink -f "$jarvis_fragment" 2>/dev/null || true)"
jarvis_unit_real="$(readlink -f "$JARVIS_ROOT/systemd/jarvis.service" 2>/dev/null || true)"
[[ -n "$jarvis_unit_real" && "$jarvis_fragment_real" == "$jarvis_unit_real" ]] || {
    echo "jarvis.service verweist auf eine andere Unit; Start aus Sicherheitsgründen abgebrochen."
    false
}
jarvis_exec="$(unit_field jarvis.service ExecStart)"
[[ "$jarvis_exec" == *"/home/alex/jarvis-venv/bin/python3"* && "$jarvis_exec" == *"$JARVIS_ROOT/jarvis_continuous.py"* ]] || {
    echo "jarvis.service startet nicht den erwarteten Backend-Prozess."
    false
}

dependency_report="$(cd "$JARVIS_ROOT" && "$RUNTIME_PYTHON" scripts/check_runtime_dependencies.py --required)" || {
    printf '%s\n' "$dependency_report"
    false
}
printf '%s\n' "$dependency_report"
if grep -q '^DEGRADED:' <<<"$dependency_report"; then degraded=1; fi
windows_powershell_dir=/mnt/c/Windows/System32/WindowsPowerShell/v1.0
[[ -x "$windows_powershell_dir/powershell.exe" ]] || {
    echo "Windows-Audio ist nicht verfügbar: powershell.exe fehlt oder ist nicht ausführbar."
    false
}
[[ -n "${WSL_INTEROP:-}" && -S "$WSL_INTEROP" ]] || {
    echo "Windows-Audio ist nicht verfügbar: Die aktuelle WSL-Session hat keinen gültigen Interop-Socket."
    false
}
manager_path="$(systemctl --user show-environment | sed -n 's/^PATH=//p')"
[[ -n "$manager_path" ]] || { echo "Der systemd User-Manager meldet keinen PATH."; false; }
if [[ ":$manager_path:" != *":$windows_powershell_dir:"* ]]; then
    manager_path="$manager_path:$windows_powershell_dir"
fi
systemctl --user set-environment "PATH=$manager_path"
systemctl --user import-environment WSL_INTEROP

jarvis_has_windows_audio_env() {
    local pid="$1" entry runtime_path='' runtime_interop=''
    [[ "$pid" =~ ^[1-9][0-9]*$ && -r "$PROC_ROOT/$pid/environ" ]] || return 1
    while IFS= read -r -d '' entry; do
        case "$entry" in
            PATH=*) runtime_path="${entry#PATH=}" ;;
            WSL_INTEROP=*) runtime_interop="${entry#WSL_INTEROP=}" ;;
        esac
    done <"$PROC_ROOT/$pid/environ"
    [[ ":$runtime_path:" == *":$windows_powershell_dir:"* && -n "$runtime_interop" ]]
}
if ! command -v wslpath >/dev/null || ! command -v powershell.exe >/dev/null; then
    echo "DEGRADED: Windows-Audio-Brücke (wslpath/powershell.exe) ist nicht vollständig verfügbar."
    degraded=1
fi
jarvis_state="$(unit_field jarvis.service ActiveState)"
if [[ "$jarvis_state" == active ]] && ! jarvis_has_windows_audio_env "$(unit_field jarvis.service MainPID)"; then
    started_jarvis=1
    systemctl --user restart jarvis.service
elif [[ "$jarvis_state" != active ]]; then
    started_jarvis=1
    systemctl --user start jarvis.service
fi

# A running unit alone is not READY. Wait for the real listener startup marker.
ready=0
invocation_id="$(unit_field jarvis.service InvocationID)"
[[ -n "$invocation_id" ]] || { echo "JARVIS-Backend meldet keine systemd-Invocation-ID."; false; }
for _ in {1..60}; do
    if [[ "$(unit_field jarvis.service ActiveState)" != active ]]; then
        echo "JARVIS-Backend wurde inaktiv, bevor die Listener-Bereitschaft erreicht war."
        false
    fi
    if journalctl --user "_SYSTEMD_INVOCATION_ID=$invocation_id" --no-pager --output=cat 2>/dev/null | grep -F 'Continuous listening active' >/dev/null; then
        ready=1
        break
    fi
    sleep 1
done
(( ready )) || { echo "JARVIS läuft, meldet aber keine Listener-Bereitschaft; Audio/Mikrofonstatus prüfen."; false; }
jarvis_pid="$(unit_field jarvis.service MainPID)"
jarvis_has_windows_audio_env "$jarvis_pid" || {
    echo "JARVIS-Backend hat die Windows-Audio-Umgebung nicht übernommen."
    false
}
jarvis_cmd="$(tr '\0' ' ' <"$PROC_ROOT/$jarvis_pid/cmdline" 2>/dev/null || true)"
[[ "$jarvis_cmd" == *"$JARVIS_ROOT/jarvis_continuous.py"* ]] || {
    echo "Der aktive Backend-Prozess stimmt nicht mit jarvis.service überein."
    false
}

if (( degraded )); then
    state=DEGRADED
    echo "$state: Backend, lokales LLM, Chatterbox und Listener laufen; optionale Abhängigkeiten sind eingeschränkt."
else
    state=READY
    echo "$state: Backend, lokales LLM, kanonische Chatterbox und Listener sind bereit."
fi
trap - ERR
