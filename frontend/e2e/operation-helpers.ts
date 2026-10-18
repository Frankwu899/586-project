import { expect, type Page } from '@playwright/test';
import type { TaskState } from '../src/generated/contracts';

/** Wait for the user action's saved result, including persisted async tickets. */
export async function savedMutation(page: Page, suffix: string): Promise<TaskState> {
  const operation = suffix === '/recognize' ? 'recognize' : suffix.endsWith('/directions/generate') ? 'directions' : suffix.endsWith('/refine') ? 'refine' : suffix.endsWith('/outputs/generate') ? 'production' : null;
  const response = await page.waitForResponse((item) => {
    if (item.request().method() !== 'POST') return false;
    const path = new URL(item.url()).pathname;
    return operation ? path.endsWith('/operations') && item.request().postDataJSON()?.operation === operation : path.endsWith(suffix);
  });
  expect(response.ok(), await response.text()).toBeTruthy();
  if (!operation) return response.json();
  let ticket = await response.json();
  await expect.poll(async () => {
    const saved = await page.request.get(`${response.url()}/${ticket.operation_id}`);
    expect(saved.ok(), await saved.text()).toBeTruthy(); ticket = await saved.json();
    return ticket.status === 'queued' || ticket.status === 'running';
  }, { timeout: 60_000, intervals: [100, 200, 500] }).toBe(false);
  expect(ticket.result).not.toBeNull();
  return ticket.result as TaskState;
}
