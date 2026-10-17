import type { EvidenceEvent } from './generated/contracts';
import { Badge, Field } from './ui';

type VisualDetails = NonNullable<EvidenceEvent['visual_details']>;
type Subject = VisualDetails['subjects']['items'][number];
type Action = VisualDetails['actions']['items'][number];
type Presentation = VisualDetails['product_presentations']['items'][number];
type SubjectRole = NonNullable<Subject['roles']>[number];

const subjectKinds: NonNullable<Subject['kind']>[] = ['person', 'animal', 'plant', 'physical_object', 'digital_interface', 'graphic', 'environment', 'other'];
const subjectRoles: SubjectRole[] = ['product', 'presenter', 'product_user', 'context', 'other'];
const actionTypes: NonNullable<Action['action_type']>[] = ['hold', 'pick_up', 'put_down', 'open', 'close', 'pour', 'apply', 'operate', 'assemble', 'disassemble', 'wear', 'eat_drink', 'point', 'move', 'other'];
const presentationTypes: NonNullable<Presentation['presentation_type']>[] = ['appearance', 'feature_demo', 'use_case', 'result_display', 'comparison', 'packaging', 'unboxing', 'other'];
const label = (value: string) => value.replaceAll('_', ' ');

function Category<T extends string>({ name, value, options, onChange }: { name: string; value: T | null; options: T[]; onChange: (value: T | null) => void }) {
  return <Field label={name}><select value={value ?? ''} onChange={(event) => onChange(event.target.value === '' ? null : event.target.value as T)}>
    <option value="">Unknown / uncertain</option>
    {options.map((option) => <option key={option} value={option}>{label(option)}</option>)}
  </select></Field>;
}

function GroupStatus({ group }: { group: VisualDetails[keyof VisualDetails] }) {
  const statuses = { observations: 'Observations found', none_found: 'Checked; none found', not_analyzed: 'Not analyzed', failed: 'Extraction failed' };
  return <><Badge warning={group.status === 'failed' || group.status === 'not_analyzed'}>{statuses[group.status]}</Badge>{group.error && <p className="error">{group.error.message}</p>}</>;
}

/** Only editable labels are replaced. Identities, references, array shape and extraction state stay intact. */
export default function VisualDetailsEditor({ value, eventId, onChange }: { value: VisualDetails | null; eventId: string; onChange: (value: VisualDetails) => void }) {
  if (!value) return <p className="muted">Structured visual details were not analyzed for this observation.</p>;
  const updateSubject = (index: number, patch: Partial<Pick<Subject, 'kind' | 'roles' | 'label' | 'description'>>) => onChange({ ...value, subjects: { ...value.subjects, items: value.subjects.items.map((subject, position) => position === index ? { ...subject, ...patch } : subject) } });
  const updateAction = (index: number, patch: Partial<Pick<Action, 'action_type' | 'description'>>) => onChange({ ...value, actions: { ...value.actions, items: value.actions.items.map((action, position) => position === index ? { ...action, ...patch } : action) } });
  const updatePresentation = (index: number, patch: Partial<Pick<Presentation, 'presentation_type' | 'description'>>) => onChange({ ...value, product_presentations: { ...value.product_presentations, items: value.product_presentations.items.map((presentation, position) => position === index ? { ...presentation, ...patch } : presentation) } });
  const toggleRole = (index: number, role: SubjectRole) => {
    const current: SubjectRole[] = value.subjects.items[index].roles ?? [];
    const next: SubjectRole[] | null = role === 'other' ? (current.includes('other') ? null : ['other']) : current.includes(role) ? current.filter((item) => item !== role) : [...current.filter((item) => item !== 'other'), role];
    updateSubject(index, { roles: next?.length ? next as NonNullable<Subject['roles']> : null });
  };
  return <div aria-label={`Structured visual details · ${eventId}`}>
    <p className="muted">Correct observed categories and descriptions. Unknown means uncertain; other needs an explanation. IDs, relationships and extraction status remain read-only.</p>
    <fieldset><legend>Subjects · {eventId}</legend><GroupStatus group={value.subjects} />
      {value.subjects.items.map((subject, index) => <div key={subject.subject_id}>
        <p><strong>Subject {index + 1}</strong> · {subject.subject_id}</p>
        <Category name={`Subject kind · ${eventId} · ${subject.subject_id}`} value={subject.kind} options={subjectKinds} onChange={(kind) => updateSubject(index, { kind })} />
        <Field label={`Subject label · ${eventId} · ${subject.subject_id}`}><input required value={subject.label} onChange={(event) => updateSubject(index, { label: event.target.value })} /></Field>
        <Field label={`Subject description · ${eventId} · ${subject.subject_id}`} hint="Explain an other category or role; preserve uncertainty in your description."><textarea value={subject.description ?? ''} onChange={(event) => updateSubject(index, { description: event.target.value || null })} /></Field>
        <fieldset><legend>Subject roles · {eventId} · {subject.subject_id}</legend><div className="roles">
          <label><input type="checkbox" checked={subject.roles === null} onChange={() => updateSubject(index, { roles: null })} />Unknown / uncertain</label>
          {subjectRoles.map((role) => <label key={role}><input type="checkbox" checked={subject.roles?.includes(role) ?? false} onChange={() => toggleRole(index, role)} />{label(role)}</label>)}
        </div></fieldset>
      </div>)}
    </fieldset>
    <fieldset><legend>Visible actions · {eventId}</legend><GroupStatus group={value.actions} />
      {value.actions.items.map((action, index) => <div key={index}>
        <p className="muted">Action {index + 1} · Actors: {action.actor_subject_ids.join(', ') || 'unlinked'} · Targets: {action.target_subject_ids.join(', ') || 'unlinked'}</p>
        <Category name={`Action type · ${eventId} · ${index + 1}`} value={action.action_type} options={actionTypes} onChange={(action_type) => updateAction(index, { action_type })} />
        <Field label={`Action description · ${eventId} · ${index + 1}`}><textarea required value={action.description} onChange={(event) => updateAction(index, { description: event.target.value })} /></Field>
      </div>)}
    </fieldset>
    <fieldset><legend>Product presentations · {eventId}</legend><GroupStatus group={value.product_presentations} />
      {value.product_presentations.items.map((presentation, index) => <div key={index}>
        <p className="muted">Presentation {index + 1} · Products: {presentation.product_subject_ids.join(', ')}</p>
        <Category name={`Presentation type · ${eventId} · ${index + 1}`} value={presentation.presentation_type} options={presentationTypes} onChange={(presentation_type) => updatePresentation(index, { presentation_type })} />
        <Field label={`Presentation description · ${eventId} · ${index + 1}`}><textarea required value={presentation.description} onChange={(event) => updatePresentation(index, { description: event.target.value })} /></Field>
      </div>)}
    </fieldset>
  </div>;
}
