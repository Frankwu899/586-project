import { cloneElement, isValidElement, useId, type ReactNode } from 'react';

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  const id = useId();
  const control = isValidElement<{ id?: string; 'aria-describedby'?: string }>(children)
    ? cloneElement(children, { id, 'aria-describedby': hint ? `${id}-hint` : undefined }) : children;
  return <div className="field"><label htmlFor={id}>{label}</label>{control}{hint && <small id={`${id}-hint`}>{hint}</small>}</div>;
}

export function Badge({ children, warning = false }: { children: ReactNode; warning?: boolean }) {
  return <span className={`badge${warning ? ' warning' : ''}`}>{children}</span>;
}

export const lines = (value: string) => value.split('\n').map((line) => line.trim()).filter(Boolean);
export const seconds = (value: number) => `${Number(value.toFixed(2))}s`;
export type Mutate = (path: string, payload?: Record<string, unknown> | FormData) => Promise<boolean>;
