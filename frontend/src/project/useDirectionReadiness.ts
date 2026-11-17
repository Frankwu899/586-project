import { useEffect, useState } from 'react';
import type { Project } from './contracts';
import { call } from './client';

interface DirectionReadiness {
  project_version: number;
  direction_current: boolean;
  code: string | null;
  message: string | null;
  direction_id: string | null;
  revision: number | null;
}

const requests = new Map<string, Promise<DirectionReadiness>>();

export function useDirectionReadiness(project: Project, contentId?: string) {
  const key = contentId ? `${project.id}:${contentId}:${project.version}` : '';
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState<{ key: string; value: DirectionReadiness | null; error: string } | null>(null);
  useEffect(() => {
    if (!contentId) return;
    let current = true;
    let request = requests.get(key);
    if (!request) {
      request = call<DirectionReadiness>(`/${project.id}/contents/${contentId}/readiness`);
      requests.set(key, request);
      if (requests.size > 32) requests.delete(requests.keys().next().value!);
    }
    void request.then(value => {
      if (current) setResult({ key, value: value.project_version === project.version ? value : null, error: '' });
    }).catch(error => {
      requests.delete(key);
      if (current) setResult({ key, value: null, error: error instanceof Error ? error.message : 'Current direction inputs could not be checked.' });
    });
    return () => { current = false; };
  }, [key, project.id, project.version, contentId, attempt]);
  const checkAgain = () => { requests.delete(key); setResult(null); setAttempt(value => value + 1); };
  return { readiness: result?.key === key ? result.value : null, readinessError: result?.key === key ? result.error : '', checkAgain };
}
