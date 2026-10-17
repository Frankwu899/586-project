import { useState } from 'react';
import type { BrandTaskBrief } from './generated/contracts';
import { Field, lines, type Mutate } from './ui';

type Props = { brief?: BrandTaskBrief; mutate: Mutate; busy: boolean };

export default function BriefEditor({ brief, mutate, busy }: Props) {
  const [values, setValues] = useState({
    brand_company: brief?.brand_company ?? '',
    product: brief?.product ?? '',
    selling_points: brief?.selling_points.join('\n') ?? '',
    approved_messages: brief?.approved_messages.join('\n') ?? '',
    target_audience: brief?.target_audience ?? '',
    platform: brief?.platform ?? '',
    communication_goal: brief?.communication_goal ?? '',
    target_duration_seconds: String(brief?.target_duration_seconds ?? 15),
    available_footage: brief?.available_footage ?? '',
    presenters: brief?.presenters ?? '',
    locations: brief?.locations ?? '',
    tone: brief?.tone ?? '',
    production_limits: brief?.production_limits ?? '',
    prohibited_claims: brief?.prohibited_claims.join('\n') ?? '',
  });
  const update = (key: keyof typeof values, value: string) => setValues((previous) => ({ ...previous, [key]: value }));
  return <section className="panel" aria-labelledby="brand-brief-heading">
    <h2 id="brand-brief-heading">1. Brand/task brief</h2>
    <p className="muted">Your inputs for the new video. {brief ? `Saved revision ${brief.revision}. Changes create a revision and mark dependent work outdated.` : 'Save your brief, or load the fictional sample below to begin with example inputs.'}</p>
    <form onSubmit={async (event) => {
      event.preventDefault();
      await mutate('/brief', { brief: { ...values, selling_points: lines(values.selling_points), approved_messages: lines(values.approved_messages), prohibited_claims: lines(values.prohibited_claims), target_duration_seconds: Number(values.target_duration_seconds) } });
    }}>
      <fieldset disabled={busy}>
        <div className="grid">
          <Field label="Brand/company"><input required value={values.brand_company} onChange={(event) => update('brand_company', event.target.value)} /></Field>
          <Field label="Product"><input required value={values.product} onChange={(event) => update('product', event.target.value)} /></Field>
          <Field label="Selling points" hint="One point per line."><textarea required value={values.selling_points} onChange={(event) => update('selling_points', event.target.value)} /></Field>
          <Field label="Approved messages" hint="One approved message per line. Include only claims approved for your new video."><textarea value={values.approved_messages} onChange={(event) => update('approved_messages', event.target.value)} /></Field>
          <Field label="Target audience"><input required value={values.target_audience} onChange={(event) => update('target_audience', event.target.value)} /></Field>
          <Field label="Publishing platform"><input required value={values.platform} onChange={(event) => update('platform', event.target.value)} /></Field>
          <Field label="Communication goal"><textarea required value={values.communication_goal} onChange={(event) => update('communication_goal', event.target.value)} /></Field>
          <Field label="Target duration (seconds)" hint="15 seconds is an editable setup default."><input type="number" min="0.1" step="0.1" required value={values.target_duration_seconds} onChange={(event) => update('target_duration_seconds', event.target.value)} /></Field>
        </div>
        <details><summary>Optional production constraints</summary><div className="grid">
          <Field label="Available footage"><textarea value={values.available_footage} onChange={(event) => update('available_footage', event.target.value)} /></Field>
          <Field label="Presenters"><input value={values.presenters} onChange={(event) => update('presenters', event.target.value)} /></Field>
          <Field label="Locations"><input value={values.locations} onChange={(event) => update('locations', event.target.value)} /></Field>
          <Field label="Tone"><input value={values.tone} onChange={(event) => update('tone', event.target.value)} /></Field>
          <Field label="Production limits"><textarea value={values.production_limits} onChange={(event) => update('production_limits', event.target.value)} /></Field>
          <Field label="Prohibited claims" hint="One claim per line."><textarea value={values.prohibited_claims} onChange={(event) => update('prohibited_claims', event.target.value)} /></Field>
        </div></details>
        <button type="submit">Save brand/task brief</button>
      </fieldset>
    </form>
  </section>;
}
