import { invoke, isTauri } from '@tauri-apps/api/core';

export interface SystemInfo {
  os: string;
  os_version: string;
  architecture: string;
  cpu: string;
  logical_cpu_count: number;
  python_version: string;
  app_version: string;
  data_directory: string;
  language: 'en';
}

export async function fetchSystem(signal: AbortSignal): Promise<SystemInfo> {
  const base = isTauri()
    ? await invoke<string>('backend_url')
    : (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8765').replace(/\/$/, '');
  const request = async (route: string) => {
    const response = await fetch(`${base}${route}`, { signal, headers: { Accept: 'application/json' } });
    if (!response.ok) throw new Error('The local API request failed.');
    return response.json();
  };
  const health = await request('/health');
  if (health.status !== 'ok' || health.service !== 'vision-studio-backend') {
    throw new Error('The local service is not a Vision Studio backend.');
  }
  const info = await request('/system/info');
  if (info.language !== 'en' || typeof info.os !== 'string' || typeof info.data_directory !== 'string') {
    throw new Error('The local API returned invalid system information.');
  }
  return info as SystemInfo;
}
