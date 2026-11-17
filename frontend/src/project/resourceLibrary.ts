import type { Project, Resource, ResourceFolder } from './contracts';

export function folderIsTrashed(project: Project, id: string | null | undefined): boolean {
  const seen = new Set<string>();
  while (id && !seen.has(id)) {
    seen.add(id);
    const folder = project.resource_folders.find(item => item.id === id);
    if (!folder) return true;
    if (folder.trashed_at) return true;
    id = folder.parent_id;
  }
  return false;
}
export function recordedImportDate(resource: Resource): string | null {
  if (resource.origin !== 'legacy') return resource.created_at || null;
  const legacy = resource.media_metadata.legacy_video;
  return legacy && typeof legacy === 'object' && typeof (legacy as Record<string, unknown>).created_at === 'string' ? (legacy as Record<string, string>).created_at : null;
}
export const resourceIsTrashed = (project: Project, resource: Resource) => Boolean(resource.trashed_at) || folderIsTrashed(project, resource.folder_id);
export function folderContains(project: Project, ancestor: string, folderId: string): boolean {
  const seen = new Set<string>(); let current: string | null | undefined = folderId;
  while (current && !seen.has(current)) {
    if (current === ancestor) return true;
    seen.add(current); current = project.resource_folders.find(item => item.id === current)?.parent_id;
  }
  return false;
}
export function folderPath(project: Project, folder: ResourceFolder): string {
  const names = [folder.name]; const seen = new Set([folder.id]); let parent = folder.parent_id;
  while (parent && !seen.has(parent)) {
    seen.add(parent); const item = project.resource_folders.find(value => value.id === parent);
    if (!item) break;
    names.unshift(item.name); parent = item.parent_id;
  }
  return names.join(' / ');
}
export function fileSize(resource: Resource): string {
  if (!resource.size_bytes && resource.status === 'missing') return '—';
  const bytes = resource.size_bytes;
  return bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : bytes >= 1024 ? `${(bytes / 1024).toFixed(1)} KB` : `${bytes} B`;
}
