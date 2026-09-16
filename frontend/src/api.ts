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
  base_model: BaseModel;
  language: 'en';
}

export interface BaseModel {
  status: 'ready';
  id: 'yolo11n';
  display_name: 'YOLO11 Nano';
  task: 'object_detection';
  file_name: 'yolo11n.pt';
  path: string;
  byte_size: number;
  sha256: string;
  distribution: 'bundled';
  load_verified: boolean;
  license: string;
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

export type CatalogTask = 'detect' | 'pose' | 'segment' | 'classify';
export type CatalogModelStatus = 'BUILT_IN' | 'AVAILABLE' | 'DOWNLOADING' | 'INSTALLED' | 'ERROR' | 'UPDATE_AVAILABLE';
export interface CatalogModel {
  id: string; name: string; category: string; description: string; task: CatalogTask;
  source_type: 'builtin' | 'downloadable'; classes: string[]; class_filter: string[];
  base_model_id: string | null; recommended_confidence: number; recommended_iou: number;
  fine_tuning_recommended: boolean; model_version: string; source: string; source_url: string | null;
  author: string; license: string; dataset_license: string; redistribution_allowed: boolean | null;
  expected_filename: string | null; download_url: string | null; checksum: string | null;
  status: CatalogModelStatus; install_error: string | null;
}
export const listModelCatalog = (category?: string, query?: string, signal?: AbortSignal) => {
  const params = new URLSearchParams(); if (category) params.set('category', category); if (query) params.set('query', query);
  return call<{ models: CatalogModel[]; categories: string[] }>(`/model-catalog${params.size ? `?${params}` : ''}`, { signal });
};
export const selectCatalogModel = (projectId: string, modelId: string) =>
  call<{ model: CatalogModel; settings: { confidence: number; iou_threshold: number; class_filter: string[]; model_version: string }; project_id: string }>(`/model-catalog/projects/${encodeURIComponent(projectId)}/selection`, { method: 'PUT', body: JSON.stringify({ model_id: modelId }) });
export const createProjectFromCatalog = (modelId: string, draft: ProjectDraft) =>
  call<Project>(`/model-catalog/models/${encodeURIComponent(modelId)}/projects`, { method: 'POST', body: JSON.stringify(draft) });

export interface DemoDataset {
  id: 'apple'; name: string; source_name: string; source_url: string; license: string;
  image_count: number; class_name: string; archive_bytes: number;
  status: 'not_started' | 'downloading' | 'importing' | 'completed' | 'failed';
  progress: number; message: string; project_id: string | null; error: string | null;
}
export const getAppleDemoDataset = (signal?: AbortSignal) => call<DemoDataset>('/demo-datasets/apple', { signal });
export const startAppleDemoDataset = () => call<DemoDataset>('/demo-datasets/apple', { method: 'POST' });

export type TrainingJobStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
export interface TrainingJob {
  id: string;
  project_id: string;
  status: TrainingJobStatus;
  model: 'yolo11n';
  epochs: number;
  imgsz: number;
  device: 'auto';
  progress: number;
  metrics: Record<string, number> | null;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
}
export interface TrainingJobDraft {
  model: 'yolo11n';
  epochs: number;
  imgsz: number;
}

const trainingJobsRoute = (projectId: string) =>
  `/projects/${encodeURIComponent(projectId)}/training-jobs`;

export const createTrainingJob = (projectId: string, draft: TrainingJobDraft) =>
  call<TrainingJob>(trainingJobsRoute(projectId), { method: 'POST', body: JSON.stringify(draft) });

export const startTrainingJob = (projectId: string, jobId: string) =>
  call<TrainingJob>(`${trainingJobsRoute(projectId)}/${encodeURIComponent(jobId)}/start`, { method: 'POST' });

export const getTrainingJob = (projectId: string, jobId: string, signal?: AbortSignal) =>
  call<TrainingJob>(`${trainingJobsRoute(projectId)}/${encodeURIComponent(jobId)}`, { signal });

export const listTrainingJobs = (projectId: string, signal?: AbortSignal) =>
  call<{ jobs: TrainingJob[]; total: number; offset: number; limit: number }>(trainingJobsRoute(projectId), { signal });

export const cancelTrainingJob = (projectId: string, jobId: string) =>
  call<TrainingJob>(`${trainingJobsRoute(projectId)}/${encodeURIComponent(jobId)}/cancel`, { method: 'POST' });

export type RegisteredModelStatus = 'development' | 'production' | 'archived';
export interface RegisteredModel {
  id: string; project_id: string; training_job_id: string | null; name: string; version: number;
  status: RegisteredModelStatus; path: string; dataset_export_id: string | null;
  settings: Record<string, string | number>; metrics: Record<string, number>; created_at: string; active: boolean;
}
const projectModelsRoute = (projectId: string) => `/projects/${encodeURIComponent(projectId)}/models`;
export const listRegisteredModels = (projectId: string, signal?: AbortSignal) =>
  call<{ models: RegisteredModel[]; active_model_id: string | null }>(projectModelsRoute(projectId), { signal });
export const activateRegisteredModel = (projectId: string, modelId: string) =>
  call<RegisteredModel>(`${projectModelsRoute(projectId)}/${encodeURIComponent(modelId)}/activate`, { method: 'POST' });
export const archiveRegisteredModel = (projectId: string, modelId: string) =>
  call<RegisteredModel>(`${projectModelsRoute(projectId)}/${encodeURIComponent(modelId)}/archive`, { method: 'POST' });

export interface UsbCamera { id: string; index: number; name: string; source_type: 'usb' }
export const listUsbCameras = (signal?: AbortSignal) =>
  call<{ cameras: UsbCamera[]; scanned: number }>('/cameras/usb', { signal });

export interface CameraDetection {
  class_id: number; class_name: string; confidence: number;
  x: number; y: number; width: number; height: number;
}
export interface CameraSession {
  id: string; project_id: string; camera_index: number;
  status: 'starting' | 'running' | 'failed' | 'stopped';
  inference_status: 'ready' | 'no_active_model' | 'unavailable';
  active_model_id: string | null; active_model_source: 'custom' | 'catalog' | 'none'; active_catalog_model_id: string | null; recommended_confidence: number; frame_id: number;
  frame_width: number | null; frame_height: number | null; fps: number;
  detections: CameraDetection[]; error: string | null;
}
const cameraSessionsRoute = (projectId: string) => `/projects/${encodeURIComponent(projectId)}/cameras/usb`;
export const startCameraSession = (projectId: string, cameraIndex: number) =>
  call<CameraSession>(`${cameraSessionsRoute(projectId)}/${cameraIndex}/sessions`, { method: 'POST' });
export const getCameraSession = (projectId: string, sessionId: string, signal?: AbortSignal) =>
  call<CameraSession>(`${cameraSessionsRoute(projectId)}/sessions/${encodeURIComponent(sessionId)}`, { signal });
export const stopCameraSession = (projectId: string, sessionId: string) =>
  call<void>(`${cameraSessionsRoute(projectId)}/sessions/${encodeURIComponent(sessionId)}`, { method: 'DELETE' });
export interface CameraFrame { id: number; image_url: string; detections: CameraDetection[] }
export async function readCameraFrame(projectId: string, sessionId: string, after: number, signal?: AbortSignal): Promise<CameraFrame | null> {
  const response = await fetch(`${await apiBase()}${cameraSessionsRoute(projectId)}/sessions/${encodeURIComponent(sessionId)}/frame?after=${after}`, { signal, headers: { Accept: 'image/jpeg' } });
  if (response.status === 204) return null;
  if (!response.ok) {
    let message: string = en.apiFailure;
    try { message = ((await response.json()) as { error?: { message?: string } }).error?.message ?? message; } catch { /* Use the English fallback. */ }
    throw new ApiError('camera_frame_failed', message);
  }
  const header = response.headers.get('X-Vision-Detections');
  let detections: CameraDetection[] = [];
  try { detections = header ? JSON.parse(header) as CameraDetection[] : []; } catch { /* Ignore malformed optional metadata. */ }
  return { id: Number(response.headers.get('X-Vision-Frame-Id') ?? after + 1), image_url: URL.createObjectURL(await response.blob()), detections };
}

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
