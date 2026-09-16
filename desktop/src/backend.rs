use std::{
    fs::OpenOptions,
    io::{Read, Write},
    net::{SocketAddr, TcpListener, TcpStream},
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    time::{Duration, Instant},
};

pub struct Backend {
    child: Option<Child>,
    address: String,
    pub error: Option<String>,
}

impl Backend {
    pub fn failed(error: String) -> Self {
        Self {
            child: None,
            address: String::new(),
            error: Some(error),
        }
    }

    pub fn start(resources: PathBuf, storage: &Path) -> Result<Self, String> {
        let listener = TcpListener::bind("127.0.0.1:0")
            .map_err(|_| "A local API port could not be reserved.")?;
        let port = listener
            .local_addr()
            .map_err(|_| "The local API port is unavailable.")?
            .port();
        let mut command = launch_command(resources)?;
        let log = OpenOptions::new()
            .create(true)
            .append(true)
            .open(storage.join("logs/backend-launch.log"))
            .map_err(|_| "The backend launch log could not be opened.")?;
        command
            .args(["--port", &port.to_string(), "--parent-watch"])
            .env("VISION_STUDIO_DATA_DIR", storage)
            .stdin(Stdio::piped())
            .stdout(Stdio::null())
            .stderr(Stdio::from(log));
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            command.creation_flags(0x08000000);
        }
        drop(listener);
        let child = command.spawn().map_err(|_| {
            "The backend executable could not be launched. Check the application files and logs."
        })?;
        let mut backend = Self {
            child: Some(child),
            address: format!("http://127.0.0.1:{port}"),
            error: None,
        };
        let deadline = Instant::now() + Duration::from_secs(60);
        while Instant::now() < deadline {
            backend.ensure_running()?;
            if health_ready(port) {
                return Ok(backend);
            }
            std::thread::sleep(Duration::from_millis(100));
        }
        Err("The backend did not become ready within 60 seconds. Check the logs and restart Vision Studio.".into())
    }

    fn ensure_running(&mut self) -> Result<(), String> {
        if let Some(error) = &self.error {
            return Err(error.clone());
        }
        let child = self.child.as_mut().ok_or("The backend has stopped.")?;
        match child.try_wait() {
            Ok(None) => Ok(()),
            _ => {
                let error = "The backend has stopped. Check the logs and restart Vision Studio."
                    .to_string();
                self.error = Some(error.clone());
                Err(error)
            }
        }
    }

    pub fn url(&mut self) -> Result<String, String> {
        self.ensure_running()?;
        Ok(self.address.clone())
    }

    pub fn stop(&mut self) {
        if let Some(mut child) = self.child.take() {
            drop(child.stdin.take());
            let deadline = Instant::now() + Duration::from_secs(3);
            while Instant::now() < deadline {
                if matches!(child.try_wait(), Ok(Some(_))) {
                    return;
                }
                std::thread::sleep(Duration::from_millis(50));
            }
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

impl Drop for Backend {
    fn drop(&mut self) {
        self.stop();
    }
}

#[cfg(not(dev))]
fn launch_command(resources: PathBuf) -> Result<Command, String> {
    let directory = resources.join("backend");
    let executable = directory.join("backend.exe");
    if !executable.is_file() || !directory.join("_internal").is_dir() {
        return Err("The bundled backend is missing. Reinstall Vision Studio or restore the complete application folder.".into());
    }
    let mut command = Command::new(executable);
    command.current_dir(directory);
    Ok(command)
}

#[cfg(dev)]
fn launch_command(_resources: PathBuf) -> Result<Command, String> {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).parent().unwrap();
    let python = root.join(".venv/Scripts/python.exe");
    if !python.is_file() {
        return Err("The development backend is missing. Run npm run setup:backend.".into());
    }
    let mut command = Command::new(python);
    command
        .args(["-m", "app"])
        .current_dir(root.join("backend"));
    Ok(command)
}

fn health_ready(port: u16) -> bool {
    let address = SocketAddr::from(([127, 0, 0, 1], port));
    let Ok(mut stream) = TcpStream::connect_timeout(&address, Duration::from_millis(200)) else {
        return false;
    };
    let _ = stream.set_read_timeout(Some(Duration::from_millis(300)));
    let _ = stream.set_write_timeout(Some(Duration::from_millis(300)));
    if stream
        .write_all(b"GET /health HTTP/1.0\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n")
        .is_err()
    {
        return false;
    }
    let mut response = String::new();
    if stream.take(16_384).read_to_string(&mut response).is_err() {
        return false;
    }
    valid_health_response(&response)
}

fn valid_health_response(response: &str) -> bool {
    let Some((headers, body)) = response.split_once("\r\n\r\n") else {
        return false;
    };
    if !headers
        .lines()
        .next()
        .is_some_and(|line| line.starts_with("HTTP/1.1 200 ") || line.starts_with("HTTP/1.0 200 "))
    {
        return false;
    }
    let Ok(value) = serde_json::from_str::<serde_json::Value>(body) else {
        return false;
    };
    value["status"] == "ok"
        && value["service"] == "vision-studio-backend"
        && value["version"] == env!("CARGO_PKG_VERSION")
}

#[cfg(test)]
mod tests {
    use super::valid_health_response;
    #[test]
    fn readiness_rejects_unrelated_or_failed_services() {
        assert!(valid_health_response("HTTP/1.1 200 OK\r\n\r\n{\"status\":\"ok\",\"service\":\"vision-studio-backend\",\"version\":\"0.1.0\"}"));
        assert!(!valid_health_response(
            "HTTP/1.1 200 OK\r\n\r\n{\"status\":\"ok\",\"service\":\"another-service\"}"
        ));
        assert!(!valid_health_response("HTTP/1.1 500 Error\r\n\r\n{}"));
        assert!(!valid_health_response("HTTP/1.1 200 OK\r\n\r\nnot json"));
    }
}
