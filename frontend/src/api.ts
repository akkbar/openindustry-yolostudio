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
  database_path: string;
  database_schema_version: number;
  language: 'en';
}

export interface Project {
  id: string;
  name: string;
  description: string;
  task_type: 'object_detection';
  created_at: string;
  updated_at: string;
  storage_path: string;
}

export interface ProjectDraft {
  name: string;
  description: string;
}

/** An API failure carrying the backend's English message. */
export class ApiError extends Error {
  constructor(readonly code: string, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

const apiBase = async (): Promise<string> => isTauri()
  ? invoke<string>('backend_url')
  : (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8765').replace(/\/$/, '');

async function call<T>(route: string, init: RequestInit = {}): Promise<T> {
  const base = await apiBase();
  let response: Response;
  try {
    response = await fetch(`${base}${route}`, {
      ...init,
      headers: { Accept: 'application/json', ...(init.body ? { 'Content-Type': 'application/json' } : {}), ...init.headers },
    });
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === 'AbortError') throw cause;
    throw new ApiError('unreachable', en.connectionFailure);
  }
  if (response.status === 204) return undefined as T;
  let body: unknown = null;
  try { body = await response.json(); } catch { body = null; }
  if (!response.ok) {
    const error = (body as { error?: { code?: string; message?: string } } | null)?.error;
    throw new ApiError(error?.code ?? 'request_failed', error?.message ?? en.apiFailure);
  }
  return body as T;
}

export const listProjects = (signal?: AbortSignal) =>
  call<{ projects: Project[]; total: number }>('/projects', { signal });

export const getProject = (id: string, signal?: AbortSignal) =>
  call<Project>(`/projects/${encodeURIComponent(id)}`, { signal });

export const createProject = (draft: ProjectDraft) =>
  call<Project>('/projects', { method: 'POST', body: JSON.stringify(draft) });

export const updateProject = (id: string, draft: Partial<ProjectDraft>) =>
  call<Project>(`/projects/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(draft) });

export const deleteProject = (id: string) =>
  call<void>(`/projects/${encodeURIComponent(id)}`, { method: 'DELETE' });

export interface DatasetValidation {
  valid: boolean; images: number; annotations: number; classes: number; issue_count: number;
  issues: { code: string; message: string; image_id: string | null; file_name: string | null; annotation_id: string | null }[];
}
export interface DatasetExportResult {
  exported: boolean; validation: DatasetValidation; path?: string; yaml_path?: string;
  train_images?: number; val_images?: number; seed?: number;
}
export const validateDataset = (id: string) => call<DatasetValidation>(`/projects/${encodeURIComponent(id)}/datasets/validate`, { method: 'POST' });
export const exportDataset = (id: string) => call<DatasetExportResult>(`/projects/${encodeURIComponent(id)}/datasets/export`, { method: 'POST' });

export interface ImportedImage {
  id: string; file_name: string; width: number; height: number; byte_size: number; thumbnail_url: string;
}
export interface ImageImportResult { status: 'imported' | 'duplicate'; image: ImportedImage }
export interface ProjectClass { id: string; project_id: string; class_index: number; name: string; color: string; created_at: string; annotation_count?: number }
export interface ProjectClasses { classes: ProjectClass[]; selected_class_id: string | null }
export const listClasses = (projectId: string, signal?: AbortSignal) =>
  call<ProjectClasses>(`/projects/${encodeURIComponent(projectId)}/classes`, { signal });
export const createClass = (projectId: string, name: string) =>
  call<ProjectClass>(`/projects/${encodeURIComponent(projectId)}/classes`, { method: 'POST', body: JSON.stringify({ name }) });
export const renameClass = (projectId: string, classId: string, name: string) =>
  call<ProjectClass>(`/projects/${encodeURIComponent(projectId)}/classes/${encodeURIComponent(classId)}`, { method: 'PATCH', body: JSON.stringify({ name }) });
export const deleteClass = (projectId: string, classId: string) =>
  call<void>(`/projects/${encodeURIComponent(projectId)}/classes/${encodeURIComponent(classId)}`, { method: 'DELETE' });
export const selectClass = (projectId: string, classId: string | null) =>
  call<{ selected_class_id: string | null }>(`/projects/${encodeURIComponent(projectId)}/annotation-state`, { method: 'PATCH', body: JSON.stringify({ selected_class_id: classId }) });
export interface GalleryImage extends ImportedImage { annotated: boolean; original_url: string }
export interface AnnotationBox { id: string; image_id: string; class_id: string; center_x: number; center_y: number; width: number; height: number; created_at?: string; updated_at?: string }
export interface AnnotationState { image: GalleryImage; annotations: AnnotationBox[]; revision: number; previous_image_id: string | null; next_image_id: string | null; position: number; total: number; annotated_count: number }
const annotationRoute = (project: string, image: string) => `/projects/${encodeURIComponent(project)}/datasets/images/${encodeURIComponent(image)}/annotations`;
async function annotationResult(route: string, init: RequestInit = {}): Promise<AnnotationState> {
  const result = await call<AnnotationState>(route, init);
  const base = await apiBase();
  return { ...result, image: { ...result.image, original_url: `${base}${result.image.original_url}`, thumbnail_url: `${base}${result.image.thumbnail_url}` } };
}
export const getAnnotations = (project: string, image: string, signal?: AbortSignal) => annotationResult(annotationRoute(project, image), { signal });
export const saveAnnotation = (project: string, image: string, box: AnnotationBox, revision: number, create: boolean) => annotationResult(`${annotationRoute(project, image)}${create ? '' : `/${encodeURIComponent(box.id)}`}`, {
  method: create ? 'POST' : 'PATCH', body: JSON.stringify({ ...(create ? { id: box.id } : {}), class_id: box.class_id, center_x: box.center_x, center_y: box.center_y, width: box.width, height: box.height, expected_revision: revision }), signal: AbortSignal.timeout(30_000),
});
export const removeAnnotation = (project: string, image: string, id: string, revision: number) => annotationResult(`${annotationRoute(project, image)}/${encodeURIComponent(id)}?expected_revision=${revision}`, { method: 'DELETE', signal: AbortSignal.timeout(30_000) });
export interface ImagePage { images: GalleryImage[]; total: number; offset: number; limit: number }
export async function listImages(projectId: string, offset: number, signal?: AbortSignal): Promise<ImagePage> {
  const page = await call<ImagePage>(`/projects/${encodeURIComponent(projectId)}/datasets/images?offset=${offset}&limit=60`, { signal });
  const base = await apiBase();
  return { ...page, images: page.images.map(image => ({ ...image, thumbnail_url: `${base}${image.thumbnail_url}`, original_url: `${base}${image.original_url}` })) };
}
export const deleteImage = (projectId: string, imageId: string) =>
  call<void>(`/projects/${encodeURIComponent(projectId)}/datasets/images/${encodeURIComponent(imageId)}`, { method: 'DELETE' });
export const getImportSummary = (projectId: string, signal?: AbortSignal) =>
  call<{ image_count: number }>(`/projects/${encodeURIComponent(projectId)}/datasets/summary`, { signal });
export async function importImage(projectId: string, file: File, signal: AbortSignal): Promise<ImageImportResult> {
  const result = await call<ImageImportResult>(`/projects/${encodeURIComponent(projectId)}/datasets/images?filename=${encodeURIComponent(file.name)}`, {
    method: 'POST', body: file, headers: { 'Content-Type': 'application/octet-stream' }, signal: AbortSignal.any([signal, AbortSignal.timeout(60_000)]),
  });
  return { ...result, image: { ...result.image, thumbnail_url: `${await apiBase()}${result.image.thumbnail_url}` } };
}

export async function fetchSystem(signal: AbortSignal): Promise<SystemInfo> {
  const base = await apiBase();
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
