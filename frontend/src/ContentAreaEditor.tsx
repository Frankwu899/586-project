import { useI18n } from './i18n';
import { useEffect, useRef, useState } from 'react';
import type { TaskState, VideoAsset } from './generated/contracts';
import { request } from './api';
import type { Mutate } from './ui';

type Rect = { x: number; y: number; width: number; height: number };
type Region = { revision: number; source_sha256: string | null; crop: Rect; exclusions: Rect[] };
type Suggestion = { crop: Rect; exclusions: Rect[]; message: string };
const full: Rect = { x: 0, y: 0, width: 1, height: 1 };
const rectStyle = (rect: Rect) => ({ left: `${rect.x * 100}%`, top: `${rect.y * 100}%`, width: `${rect.width * 100}%`, height: `${rect.height * 100}%` });

export default function ContentAreaEditor({ state, video, mutate, onClose }: { state: TaskState; video: VideoAsset; mutate: Mutate; onClose: () => void }) {
  const { t } = useI18n();
  const dialog = useRef<HTMLDialogElement>(null);
  const preview = useRef<HTMLVideoElement>(null);
  const [region, setRegion] = useState<Region | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [working, setWorking] = useState('');
  const [displayRatio, setDisplayRatio] = useState(`${video.width ?? 16} / ${video.height ?? 9}`);
  const path = `/tasks/${state.task.task_id}/videos/${video.video_id}/content-region`;
  useEffect(() => { dialog.current?.showModal(); }, []);
  useEffect(() => {
    let active = true;
    request<Region>(path).then((value) => { if (active) setRegion(value); }).catch((reason: Error) => { if (active) setError(reason.message); });
    return () => { active = false; };
  }, [path]);
  const suggest = async () => {
    setWorking('Checking source frames…'); setError('');
    try {
      const suggestion = await request<Suggestion>(`${path}/suggest`, {});
      setRegion((value) => value ? { ...value, crop: suggestion.crop, exclusions: suggestion.exclusions } : value);
      setNotice(suggestion.message);
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'A suggestion could not be prepared. Your source is unchanged.'); }
    finally { setWorking(''); }
  };
  const save = async () => {
    if (!region) return;
    setError(''); setWorking('Saving content area…');
    try {
      if (await mutate(`/videos/${video.video_id}/content-region`, { expected_revision: region.revision, crop: region.crop, exclusions: region.exclusions })) onClose();
      else setError('The content area could not be saved. Close and reopen this editor to load the latest task, then retry.');
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'The content area could not be saved.'); }
    finally { setWorking(''); }
  };
  const edge = (name: 'top' | 'bottom' | 'left' | 'right', value: number) => setRegion((current) => {
    if (!current) return current;
    const crop = { ...current.crop };
    if (name === 'top') { const bottom = crop.y + crop.height; crop.y = Math.min(value, bottom - .05); crop.height = bottom - crop.y; }
    if (name === 'bottom') crop.height = Math.max(.05, 1 - value - crop.y);
    if (name === 'left') { const right = crop.x + crop.width; crop.x = Math.min(value, right - .05); crop.width = right - crop.x; }
    if (name === 'right') crop.width = Math.max(.05, 1 - value - crop.x);
    return { ...current, crop };
  });
  return <dialog ref={dialog} className="content-area-dialog" onCancel={(event) => { event.preventDefault(); if (!working) onClose(); }} aria-labelledby="content-area-title">
    <header><div><h2 id="content-area-title">{t("Content area")}</h2><p>{t("Exclude recording controls. Keep captions, prices and product logos.")}</p></div><button type="button" className="secondary" onClick={onClose} disabled={Boolean(working)} aria-label={t("Close content area")}>{t("Close")}</button></header>
    <div className="content-area-layout"><div className="content-preview-column"><div className="content-preview" style={{ aspectRatio: displayRatio }}>
      <video ref={preview} onLoadedMetadata={(event) => setDisplayRatio(`${event.currentTarget.videoWidth} / ${event.currentTarget.videoHeight}`)} muted playsInline preload="metadata" src={`/api/tasks/${state.task.task_id}/media/${video.video_id}`} aria-label={t("Content-area source preview")} />
      {region && <><div className="content-crop-outline" style={rectStyle(region.crop)} />{region.exclusions.map((rect, index) => <div className="content-exclusion" key={index} style={rectStyle(rect)}><span>{index + 1}</span></div>)}</>}
    </div><div className="actions">{[0, .5, .97].map((part, index) => <button type="button" className="secondary" key={part} onClick={() => { if (preview.current) preview.current.currentTime = (video.playback?.frame_timing.media_start_seconds ?? video.frame_timing?.media_start_seconds ?? 0) + part * (video.duration_seconds ?? 0); }}>{t(['Start', 'Middle', 'End'][index])}</button>)}</div><p className="muted">{t("Preview only. Original video and audio remain unchanged.")}</p></div>
    <div className="content-area-settings">{!region && !error && <p role="status">{t("Loading saved content area…")}</p>}
      {region && <><div className="actions"><button type="button" className="secondary" onClick={() => void suggest()} disabled={Boolean(working)}>{t("Suggest content area")}</button><button type="button" className="text-button" disabled={Boolean(working)} onClick={() => { setRegion({ ...region, crop: full, exclusions: [] }); setNotice('Full frame restored in this preview. Save to apply.'); }}>{t("Restore full frame")}</button></div>
      <p className="muted">{t("Suggestions look for persistent edge bars. Review before saving; stillness alone does not identify interface noise.")}</p>
      <fieldset disabled={Boolean(working)}><legend>{t("Trim edges")}</legend>{(['top', 'bottom', 'left', 'right'] as const).map((name) => {
        const value = name === 'top' ? region.crop.y : name === 'bottom' ? 1 - region.crop.y - region.crop.height : name === 'left' ? region.crop.x : 1 - region.crop.x - region.crop.width;
        const max = name === 'top' ? region.crop.y + region.crop.height - .05 : name === 'bottom' ? 1 - region.crop.y - .05 : name === 'left' ? region.crop.x + region.crop.width - .05 : 1 - region.crop.x - .05;
        return <label className="content-edge" key={name}>{t(name)}<input type="range" min={0} max={Math.round(max * 100)} step={1} value={Math.round(value * 100)} aria-label={t("Trim {edge} percent", { edge: t(name) })} onChange={(event) => edge(name, Number(event.target.value) / 100)} /><output>{Math.round(value * 100)}%</output></label>;
      })}</fieldset>
      <details><summary>{t("Exclude floating controls ·")} {region.exclusions.length}</summary><p className="muted">{t("Rectangles use percentages of the original frame. Mask only app controls, never valid video content.")}</p>{region.exclusions.map((rect, index) => <fieldset key={index} disabled={Boolean(working)}><legend>{t("Exclusion")} {index + 1}</legend><div className="mask-coordinates">{(['x', 'y', 'width', 'height'] as const).map((key) => <label key={key}>{t(key)}<input type="number" min={key === 'width' || key === 'height' ? 1 : 0} max={100} step={1} value={Math.round(rect[key] * 100)} onChange={(event) => setRegion({ ...region, exclusions: region.exclusions.map((item, itemIndex) => { if (itemIndex !== index) return item; const next = { ...item, [key]: Math.max(key === 'width' || key === 'height' ? .01 : 0, Math.min(.99, Number(event.target.value) / 100)) }; next.width = Math.min(next.width, 1 - next.x); next.height = Math.min(next.height, 1 - next.y); return next; }) })} /></label>)}</div><button type="button" className="text-button" onClick={() => setRegion({ ...region, exclusions: region.exclusions.filter((_, itemIndex) => itemIndex !== index) })}>{t("Remove exclusion")}</button></fieldset>)}<button type="button" className="secondary" disabled={Boolean(working) || region.exclusions.length >= 8} onClick={() => setRegion({ ...region, exclusions: [...region.exclusions, { x: .82, y: .4, width: .15, height: .3 }] })}>{t("Add exclusion")}</button></details>
      </>}
      {working && <p role="status" className="local-operation"><span className="working-spinner" aria-hidden="true" />{t(working)}</p>}{notice && <p role="status" className="notice">{t(notice)}</p>}{error && <p role="alert" className="error">{t(error)}</p>}
    </div></div><footer><p>{t("Changing this area requires a new analysis. Previous results stay in history; affected approvals become historical.")}</p><button type="button" onClick={() => void save()} disabled={!region || Boolean(working)}>{t("Save content area")}</button></footer>
  </dialog>;
}
