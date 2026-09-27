#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::{
    fs,
    fs::OpenOptions,
    path::{Path, PathBuf},
    process::{Command, Stdio},
    thread,
    time::{Duration, Instant, SystemTime, UNIX_EPOCH},
};

const WEB_TOKEN_ENV: &str = "JARVIS_WEB_AUTH_TOKEN";
const SUPERVISOR_TIMEOUT: Duration = Duration::from_secs(10);
const MAX_SUPERVISOR_OUTPUT_BYTES: u64 = 256 * 1024;

fn supervisor_script() -> Result<PathBuf, String> {
    let executable = std::env::current_exe()
        .map_err(|_| "Installationspfad der Desktop-App nicht ermittelbar.".to_string())?;
    let install_dir = executable
        .parent()
        .ok_or_else(|| "Installationsverzeichnis der Desktop-App nicht ermittelbar.".to_string())?;
    let candidates = [
        install_dir.join("JARVIS-Runtime.ps1"),
        install_dir.join("runtime").join("JARVIS-Runtime.ps1"),
    ];
    candidates
        .into_iter()
        .find(|path| path.is_file())
        .and_then(|path| path.canonicalize().ok())
        .ok_or_else(|| "JARVIS-Runtime.ps1 fehlt neben der installierten Desktop-App.".into())
}

fn repository_root_config_path() -> Result<PathBuf, String> {
    let app_data = std::env::var_os("APPDATA")
        .map(PathBuf::from)
        .ok_or_else(|| "Windows-AppData ist nicht verfügbar.".to_string())?;
    Ok(app_data
        .join("JARVIS")
        .join("ControlHub")
        .join("runtime-root.txt"))
}

fn validate_repository_root(path: PathBuf) -> Result<PathBuf, String> {
    let root = path
        .canonicalize()
        .map_err(|_| "JARVIS-Repository-Pfad konnte nicht aufgelöst werden.".to_string())?;
    let required = [
        "JARVIS.Runtime.psm1",
        "config.yaml",
        "start.sh",
        "stop.sh",
        "restart.sh",
        "scripts/runtime_status.py",
        "scripts/check_runtime_dependencies.py",
        "scripts/check_chatterbox_runtime.py",
        "core/runtime_state.py",
    ];
    if required
        .iter()
        .any(|relative| !root.join(relative).is_file())
    {
        return Err(
            "Ausgewählter Ordner ist kein vollständiges JARVIS-Repository; Runtime-Dateien fehlen."
                .into(),
        );
    }
    Ok(root)
}

fn configured_repository_root() -> Result<PathBuf, String> {
    let config_path = repository_root_config_path()?;
    if let Ok(configured) = fs::read_to_string(config_path) {
        if let Ok(root) = validate_repository_root(PathBuf::from(configured.trim())) {
            return Ok(root);
        }
    }
    if let Some(path) = std::env::var_os("JARVIS_REPOSITORY_ROOT") {
        return validate_repository_root(PathBuf::from(path));
    }
    Err("JARVIS-Repository noch nicht ausgewählt.".to_string())
}

fn supervisor_repository_root(_script: &Path) -> Result<PathBuf, String> {
    configured_repository_root()
}

#[cfg(windows)]
fn powershell_executable() -> Result<PathBuf, String> {
    let system_root = std::env::var_os("SystemRoot")
        .or_else(|| std::env::var_os("WINDIR"))
        .map(PathBuf::from)
        .ok_or_else(|| "Windows-Systemverzeichnis ist nicht verfügbar.".to_string())?;
    let executable = system_root
        .join("System32")
        .join("WindowsPowerShell")
        .join("v1.0")
        .join("powershell.exe");
    if !executable.is_file() {
        return Err("Windows PowerShell wurde am Systempfad nicht gefunden.".into());
    }
    Ok(executable)
}

#[cfg(not(windows))]
fn powershell_executable() -> Result<PathBuf, String> {
    Err("Der Runtime-Supervisor benötigt Windows PowerShell.".into())
}

#[tauri::command]
fn runtime_repository_root() -> Result<Option<String>, String> {
    match configured_repository_root() {
        Ok(path) => Ok(Some(path.display().to_string())),
        Err(_) => Ok(None),
    }
}

#[tauri::command]
fn runtime_choose_repository_root() -> Result<Option<String>, String> {
    let selected = rfd::FileDialog::new()
        .set_title("Vollständiges JARVIS-Repository auswählen")
        .pick_folder();
    let Some(selected) = selected else {
        return Ok(None);
    };
    let root = validate_repository_root(selected)?;
    let config_path = repository_root_config_path()?;
    let parent = config_path
        .parent()
        .ok_or_else(|| "App-Konfigurationspfad ungültig.".to_string())?;
    fs::create_dir_all(parent)
        .map_err(|_| "JARVIS-App-Konfiguration konnte nicht angelegt werden.".to_string())?;
    fs::write(&config_path, root.to_string_lossy().as_bytes())
        .map_err(|_| "JARVIS-Repository-Pfad konnte nicht gespeichert werden.".to_string())?;
    Ok(Some(root.display().to_string()))
}

#[derive(Clone, Copy)]
enum Service {
    Web,
    LlmMain,
    LlmSmall,
    Tts,
    Flux,
    Vvs,
}

impl Service {
    fn parse(value: &str) -> Result<Self, String> {
        match value {
            "web" => Ok(Self::Web),
            "llm-main" => Ok(Self::LlmMain),
            "llm-small" => Ok(Self::LlmSmall),
            "tts" => Ok(Self::Tts),
            "flux" => Ok(Self::Flux),
            "vvs" => Ok(Self::Vvs),
            _ => Err("Unbekannter Backend-Dienst.".into()),
        }
    }

    fn base_url(self) -> Result<String, String> {
        let (env, fallback) = match self {
            Self::Web => ("JARVIS_WEB_URL", "http://127.0.0.1:8091"),
            Self::LlmMain => ("JARVIS_LLM_MAIN_URL", "http://127.0.0.1:8080"),
            Self::LlmSmall => ("JARVIS_LLM_SMALL_URL", "http://127.0.0.1:8081"),
            Self::Tts => ("JARVIS_TTS_URL", "http://127.0.0.1:8765"),
            Self::Flux => ("JARVIS_FLUX_URL", "http://127.0.0.1:8190"),
            Self::Vvs => ("JARVIS_VVS_URL", "http://127.0.0.1:8088"),
        };
        let base = std::env::var(env).unwrap_or_else(|_| fallback.to_string());
        let parsed = url::Url::parse(&base).map_err(|_| "Ungültige Backend-URL.".to_string())?;
        let host = parsed
            .host()
            .ok_or_else(|| "Backend-URL ohne Host.".to_string())?;
        let loopback = match host {
            url::Host::Domain(name) => name.eq_ignore_ascii_case("localhost"),
            url::Host::Ipv4(address) => address.is_loopback(),
            url::Host::Ipv6(address) => address.is_loopback(),
        };
        if !loopback || !matches!(parsed.scheme(), "http" | "https") {
            return Err("Backend-URLs müssen auf HTTP(S) Loopback zeigen.".into());
        }
        if !parsed.username().is_empty()
            || parsed.password().is_some()
            || parsed.query().is_some()
            || parsed.fragment().is_some()
        {
            return Err(
                "Backend-URL darf keine Zugangsdaten oder Zusatzparameter enthalten.".into(),
            );
        }
        Ok(base)
    }

    fn allows_path(self, path: &str) -> bool {
        let route = path.split('?').next().unwrap_or(path);
        match self {
            Self::Web => matches!(
                route,
                "/api/stats"
                    | "/api/agents/status"
                    | "/api/events/health"
                    | "/api/events/stt"
                    | "/api/events/tts"
                    | "/api/events/aggregate"
                    | "/api/memory/summary"
                    | "/api/metrics/summary"
                    | "/api/metrics/timeseries"
                    | "/api/metrics/tools"
                    | "/api/desktop/snapshot"
                    | "/api/desktop/live"
            ),
            Self::LlmMain => matches!(route, "/health" | "/v1/models"),
            Self::LlmSmall | Self::Tts | Self::Flux => route == "/health",
            Self::Vvs => matches!(route, "/health" | "/ready"),
        }
    }
}

fn validate_path(path: &str) -> Result<(), String> {
    if !path.starts_with('/')
        || path.starts_with("//")
        || path.contains("\\")
        || path.bytes().any(|byte| byte < 0x20)
        || path.split('/').any(|part| part == "." || part == "..")
    {
        return Err("Ungültiger Backend-Pfad.".into());
    }
    Ok(())
}

#[tauri::command]
async fn backend_get_json(
    target: String,
    path: String,
    timeout_ms: Option<u64>,
) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || {
        backend_get_json_blocking(target, path, timeout_ms)
    })
    .await
    .map_err(|_| "Native Backend-Aufgabe fehlgeschlagen.".to_string())?
}

fn backend_get_json_blocking(
    target: String,
    path: String,
    timeout_ms: Option<u64>,
) -> Result<Value, String> {
    validate_path(&path)?;
    let service = Service::parse(&target)?;
    if !service.allows_path(&path) {
        return Err("Dieser Backend-Endpunkt ist für die Desktop-UI nicht freigegeben.".into());
    }
    let timeout = Duration::from_millis(timeout_ms.unwrap_or(4000).clamp(250, 15000));
    let base = service.base_url()?;
    let url = format!("{}{}", base.trim_end_matches('/'), path);
    let agent = ureq::AgentBuilder::new().redirects(0).build();
    let mut request = agent
        .get(&url)
        .set("Accept", "application/json")
        .timeout(timeout);
    if matches!(service, Service::Web) {
        if let Ok(token) = std::env::var(WEB_TOKEN_ENV) {
            if !token.is_empty() && token != "${JARVIS_WEB_AUTH_TOKEN}" {
                request = request.set("Authorization", &format!("Bearer {token}"));
            }
        }
    }
    let response = request.call().map_err(|error| match error {
        ureq::Error::Status(code, _) => format!("Backend antwortet mit HTTP {code}."),
        ureq::Error::Transport(_) => "Backend nicht erreichbar oder Anfrage abgelaufen.".into(),
    })?;
    response
        .into_json::<Value>()
        .map_err(|_| "Backend-Antwort ist kein gültiges JSON.".into())
}

#[derive(Deserialize, Serialize)]
struct RuntimeActionResult {
    accepted: bool,
    message: String,
}

fn run_supervisor(action: &str) -> Result<String, String> {
    if !matches!(action, "getRuntime" | "start" | "stop" | "restart") {
        return Err("Nicht erlaubte Runtime-Aktion.".into());
    }
    let script = supervisor_script()?;
    let repository_root = supervisor_repository_root(&script)?;
    let mut command = Command::new(powershell_executable()?);
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x08000000); // CREATE_NO_WINDOW
    }
    let output_path = std::env::temp_dir().join(format!(
        "jarvis-supervisor-{}-{}.json",
        std::process::id(),
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_nanos(),
    ));
    let output_file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&output_path)
        .map_err(|_| "Temporäre Supervisor-Ausgabe konnte nicht angelegt werden.".to_string())?;
    let mut child = match command
        .env("JARVIS_REPOSITORY_ROOT", &repository_root)
        .args([
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            script
                .to_str()
                .ok_or_else(|| "Ungültiger Supervisor-Pfad.".to_string())?,
            "-Action",
            action,
        ])
        .current_dir(repository_root)
        .stdin(Stdio::null())
        .stdout(Stdio::from(output_file))
        .stderr(Stdio::null())
        .spawn()
    {
        Ok(child) => child,
        Err(_) => {
            let _ = fs::remove_file(&output_path);
            return Err("JARVIS-Runtime.ps1 konnte nicht gestartet werden.".into());
        }
    };
    let deadline = Instant::now() + SUPERVISOR_TIMEOUT;
    let status = loop {
        match child.try_wait() {
            Ok(Some(status)) => break status,
            Ok(None) => {}
            Err(_) => {
                let _ = child.kill();
                let _ = child.wait();
                let _ = fs::remove_file(&output_path);
                return Err("Supervisor-Prozessstatus konnte nicht gelesen werden.".into());
            }
        }
        if Instant::now() >= deadline {
            let _ = child.kill();
            let _ = child.wait();
            let _ = fs::remove_file(&output_path);
            return Err("JARVIS-Runtime.ps1 hat das Zeitlimit überschritten.".into());
        }
        match fs::metadata(&output_path) {
            Ok(metadata) if metadata.len() > MAX_SUPERVISOR_OUTPUT_BYTES => {
                let _ = child.kill();
                let _ = child.wait();
                let _ = fs::remove_file(&output_path);
                return Err("Supervisor-Ausgabe überschreitet das Größenlimit.".into());
            }
            Err(_) => {
                let _ = child.kill();
                let _ = child.wait();
                let _ = fs::remove_file(&output_path);
                return Err("Supervisor-Ausgabe ist nicht lesbar.".into());
            }
            _ => {}
        }
        thread::sleep(Duration::from_millis(25));
    };
    let output = fs::metadata(&output_path)
        .map_err(|_| "Supervisor-Ausgabe konnte nicht gelesen werden.".to_string())
        .and_then(|metadata| {
            if metadata.len() > MAX_SUPERVISOR_OUTPUT_BYTES {
                Err("Supervisor-Ausgabe überschreitet das Größenlimit.".to_string())
            } else {
                fs::read(&output_path)
                    .map_err(|_| "Supervisor-Ausgabe konnte nicht gelesen werden.".to_string())
            }
        });
    let _ = fs::remove_file(&output_path);
    let output = output?;
    if !status.success() {
        return Err("JARVIS-Runtime.ps1 hat die Anfrage abgelehnt.".into());
    }
    String::from_utf8(output).map_err(|_| "Supervisor lieferte ungültiges UTF-8.".into())
}

#[tauri::command]
async fn runtime_get() -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(runtime_get_blocking)
        .await
        .map_err(|_| "Native Supervisor-Aufgabe fehlgeschlagen.".to_string())?
}

fn runtime_get_blocking() -> Result<Value, String> {
    serde_json::from_str(&run_supervisor("getRuntime")?)
        .map_err(|_| "Supervisor lieferte ungültiges JSON.".into())
}

async fn runtime_action(action: &'static str) -> Result<RuntimeActionResult, String> {
    tauri::async_runtime::spawn_blocking(move || runtime_action_blocking(action))
        .await
        .map_err(|_| "Native Supervisor-Aufgabe fehlgeschlagen.".to_string())?
}

fn runtime_action_blocking(action: &str) -> Result<RuntimeActionResult, String> {
    serde_json::from_str(&run_supervisor(action)?)
        .map_err(|_| "Supervisor lieferte ungültiges JSON.".into())
}

#[tauri::command]
async fn runtime_start() -> Result<RuntimeActionResult, String> {
    runtime_action("start").await
}

#[tauri::command]
async fn runtime_stop() -> Result<RuntimeActionResult, String> {
    runtime_action("stop").await
}

#[tauri::command]
async fn runtime_restart() -> Result<RuntimeActionResult, String> {
    runtime_action("restart").await
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            backend_get_json,
            runtime_get,
            runtime_start,
            runtime_stop,
            runtime_restart,
            runtime_repository_root,
            runtime_choose_repository_root
        ])
        .run(tauri::generate_context!())
        .expect("J.A.R.V.I.S Desktop konnte nicht gestartet werden");
}

#[cfg(test)]
mod tests {
    use super::Service;

    #[test]
    fn web_transport_only_allows_the_privacy_safe_agent_status_route() {
        assert!(Service::Web.allows_path("/api/agents/status"));
        assert!(!Service::Web.allows_path("/api/agents/status/extra"));
        assert!(Service::Web.allows_path("/api/agents/status?ignored=true"));
    }
}
