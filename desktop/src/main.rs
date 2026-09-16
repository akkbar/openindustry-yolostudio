#![windows_subsystem = "windows"]

mod backend;

use backend::Backend;
use serde::Serialize;
use std::{
    fs::{self, OpenOptions},
    io::Write,
    path::PathBuf,
    process::Command,
    sync::Mutex,
};
use tauri::Manager;

struct Studio {
    backend: Mutex<Backend>,
    storage: PathBuf,
}

#[derive(Serialize)]
struct DesktopInfo {
    version: &'static str,
    mode: &'static str,
    startup_error: Option<String>,
}

#[tauri::command]
fn backend_url(studio: tauri::State<'_, Studio>) -> Result<String, String> {
    studio
        .backend
        .lock()
        .map_err(|_| "Backend state is unavailable.")?
        .url()
}

#[tauri::command]
fn desktop_info(studio: tauri::State<'_, Studio>) -> DesktopInfo {
    DesktopInfo {
        version: env!("CARGO_PKG_VERSION"),
        mode: if !cfg!(dev) {
            "packaged"
        } else {
            "development"
        },
        startup_error: studio
            .backend
            .lock()
            .ok()
            .and_then(|backend| backend.error.clone()),
    }
}

#[tauri::command]
fn open_app_folder(kind: &str, studio: tauri::State<'_, Studio>) -> Result<(), String> {
    let folder = match kind {
        "data" => studio.storage.clone(),
        "logs" => studio.storage.join("logs"),
        _ => return Err("Unknown application folder.".into()),
    };
    Command::new("explorer.exe")
        .arg(folder)
        .spawn()
        .map_err(|_| "The application folder could not be opened.")?;
    Ok(())
}

fn main() {
    let app = tauri::Builder::default()
        .setup(|app| {
            let storage = match std::env::var_os("VISION_STUDIO_DATA_DIR") {
                Some(value) => {
                    let path = PathBuf::from(value);
                    if !path.is_absolute() {
                        return Err("VISION_STUDIO_DATA_DIR must be an absolute path.".into());
                    }
                    path
                }
                None => app.path().local_data_dir()?.join("VisionStudio"),
            };
            fs::create_dir_all(storage.join("logs"))?;
            let log_path = storage.join("logs/desktop.log");
            if fs::metadata(&log_path)
                .map(|m| m.len() > 2_000_000)
                .unwrap_or(false)
            {
                let _ = fs::copy(&log_path, storage.join("logs/desktop.previous.log"));
                let _ = fs::write(&log_path, "");
            }
            let mut log = OpenOptions::new()
                .create(true)
                .append(true)
                .open(log_path)?;
            writeln!(log, "Starting OpenIndustry Vision Studio {}", env!("CARGO_PKG_VERSION"))?;
            let backend =
                Backend::start(app.path().resource_dir()?, &storage).unwrap_or_else(|error| {
                    let _ = writeln!(log, "Backend startup failed: {error}");
                    Backend::failed(error)
                });
            if backend.error.is_none() {
                writeln!(log, "Backend ready. Opening the application window.")?;
            }
            app.manage(Studio {
                backend: Mutex::new(backend),
                storage: storage.clone(),
            });
            tauri::WebviewWindowBuilder::from_config(app, &app.config().app.windows[0])?
                .data_directory(storage.join("webview"))
                .build()?;
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            backend_url,
            desktop_info,
            open_app_folder
        ])
        .build(tauri::generate_context!())
        .expect("OpenIndustry Vision Studio could not start.");
    app.run(|app, event| {
        if matches!(event, tauri::RunEvent::Exit) {
            if let Ok(mut backend) = app.state::<Studio>().backend.lock() {
                backend.stop();
            }
        }
    });
}
