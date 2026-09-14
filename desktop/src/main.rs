#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::{
    net::TcpListener,
    path::Path,
    process::{Child, Command, Stdio},
    sync::Mutex,
};
use tauri::Manager;

struct Backend {
    child: Mutex<Option<Child>>,
    url: String,
}

impl Backend {
    fn start() -> Result<Self, Box<dyn std::error::Error>> {
        // Phase 0 uses the repository virtual environment. Phase 2 replaces this
        // launcher with the packaged sidecar, without changing the frontend API.
        let root = Path::new(env!("CARGO_MANIFEST_DIR")).parent().unwrap();
        let python = root.join(if cfg!(windows) {
            ".venv/Scripts/python.exe"
        } else {
            ".venv/bin/python"
        });
        if !python.is_file() {
            return Err("Backend environment is missing. Run npm run setup:backend first.".into());
        }
        let listener = TcpListener::bind("127.0.0.1:0")?;
        let port = listener.local_addr()?.port();
        let mut command = Command::new(python);
        command
            .args(["-m", "app", "--port", &port.to_string()])
            .current_dir(root.join("backend"))
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null());
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            command.creation_flags(0x08000000); // CREATE_NO_WINDOW
        }
        drop(listener);
        let child = command.spawn()?;
        Ok(Self {
            child: Mutex::new(Some(child)),
            url: format!("http://127.0.0.1:{port}"),
        })
    }

    fn stop(&self) {
        if let Ok(mut guard) = self.child.lock() {
            if let Some(mut child) = guard.take() {
                let _ = child.kill();
                let _ = child.wait();
            }
        }
    }
}

impl Drop for Backend {
    fn drop(&mut self) {
        self.stop();
    }
}

#[tauri::command]
fn backend_url(backend: tauri::State<'_, Backend>) -> Result<String, String> {
    let mut guard = backend.child.lock().map_err(|_| "Backend state is unavailable.")?;
    let child = guard.as_mut().ok_or("Backend has stopped.")?;
    match child.try_wait() {
        Ok(None) => Ok(backend.url.clone()),
        _ => Err("Backend could not start. Check the backend log and restart Vision Studio.".into()),
    }
}

fn main() {
    let app = tauri::Builder::default()
        .setup(|app| {
            app.manage(Backend::start()?);
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![backend_url])
        .build(tauri::generate_context!())
        .expect("Vision Studio could not start.");
    app.run(|app, event| {
        if matches!(event, tauri::RunEvent::Exit) {
            app.state::<Backend>().stop();
        }
    });
}
