import { invoke, isTauri } from '@tauri-apps/api/core';
import { APP_VERSION, en } from './locales/en';

export interface DesktopInfo {
  version: string;
  mode: 'packaged' | 'development' | 'browser';
  startup_error: string | null;
}

export const getDesktopInfo = (): Promise<DesktopInfo> => isTauri()
  ? invoke<DesktopInfo>('desktop_info')
  : Promise.resolve({ version: APP_VERSION, mode: 'browser', startup_error: null });

export const openAppFolder = (kind: 'data' | 'logs') => invoke('open_app_folder', { kind });

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
    if (!response.ok) throw new Error(en.apiFailure);
    return response.json();
  };
  const health = await request('/health');
  if (health.status !== 'ok' || health.service !== 'vision-studio-backend') {
    throw new Error(en.serviceMismatch);
  }
  const info = await request('/system/info');
  if (info.language !== 'en' || typeof info.os !== 'string' || typeof info.data_directory !== 'string') {
    throw new Error(en.invalidSystem);
  }
  return info as SystemInfo;
}
