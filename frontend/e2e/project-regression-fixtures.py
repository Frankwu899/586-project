"""Authored offline browser fixtures. These are not recognition-quality results."""
import hashlib
from pathlib import Path
import shutil
import sys
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.app.project_workspace.models import (  # noqa: E402
    Analysis, BriefRevision, ContentItem, Direction, EvidenceEvent,
    EvidenceRevision, Fact, InputManifest, Job, ProductionPack, Resource, Selection,
)
from backend.app.project_workspace.store import ProjectStore  # noqa: E402

store = ProjectStore(Path(sys.argv[1]))
mode = sys.argv[2]
if mode == 'seed':
    original = Path(sys.argv[3])
    project = store.create('Synthetic 1.8.1 browser review ' + uuid4().hex[:8])
    ids = []
    def populate(state):
        for index, name in enumerate(('Synthetic blue reference.mp4', 'Synthetic second reference.mp4')):
            resource = Resource(name=name, kind='video', original_path='sources/media/placeholder.mp4',
                sha256=hashlib.sha256(original.read_bytes()).hexdigest(), size_bytes=original.stat().st_size,
                mime_type='video/mp4', duration_seconds=12, status='partial' if index == 0 else 'ready')
            resource.original_path = f'sources/media/{resource.id}.mp4'
            shutil.copyfile(original, store.resolve_path(state.id, resource.original_path))
            resource.evidence = [EvidenceRevision(revision=1, reviewed=True,
                events=[EvidenceEvent(id=f'speech_{n}', kind='speech', text=f'Authored transcript fixture line {n + 1}: the saved source wording stays readable in a short window.', start_seconds=(n % 10), end_seconds=(n % 10) + 1) for n in range(32)] + [
                    EvidenceEvent(id='visual_1', kind='visual', text='A synthetic blue frame fills the picture.', start_seconds=2, end_seconds=3),
                    EvidenceEvent(id='visual_2', kind='visual', text='The synthetic blue frame continues.', start_seconds=6, end_seconds=7)],
                coverage={'speech': 'failed' if index == 0 else 'complete', 'visual': 'complete', 'on_screen_text': 'complete', 'music': 'not_analyzed'},
                limitations=['Authored fixture; no live recognition was performed.'] + [f'Coverage note {n + 1}: sparse sampling cannot establish unseen action.' for n in range(16)])]
            state.resources.append(resource)
            ids.append(resource.id)
        state.selection = Selection(resource_ids=ids)
        state.briefs = [BriefRevision(revision=1, facts=[Fact(key='assignment', value='Prepare a short abstract blue study.', status='confirmed')])]
        item = ContentItem(title='Standalone blue study', description='Authored browser test content')
        direction = Direction(title='A sustained frame', concept='Hold the blue frame for twelve seconds.', approved=True)
        item.directions = [direction]
        item.approved_direction_id, item.approved_direction_revision = direction.id, 1
        state.contents = [item]
        state.active_content_id = item.id
        state.packs = [ProductionPack(content_id=item.id, inputs=InputManifest(brief_revision=1, direction_id=direction.id, direction_revision=1), production_brief='Capture the twelve-second abstract study.', script='A blue frame.', storyboard='Original storyboard text.', shot_list='01: Hold the blue frame.')]
        sources = [dict(resource_id=rid, evidence_revision=1, event_id='visual_1', start_seconds=2, end_seconds=3, locator='Fixture observation', excerpt='A synthetic blue frame fills the picture.') for rid in ids]
        structures = [dict(resource_id=rid, summary='A sustained image without a forced marketing sequence.', nodes=[dict(id='first', kind='observation', label='Blue frame introduced', detail='Observed frame at two seconds.', sources=[sources[index]]), dict(id='second', kind='observation', label='Blue frame held', detail='Observed frame at six seconds.', sources=[dict(**{**sources[index], 'event_id':'visual_2', 'start_seconds':6, 'end_seconds':7})])], edges=[dict(source='first', target='second', label='Continues', explanation='The same image remains visible at both sampled moments.')]) for index, rid in enumerate(ids)]
        common = dict(inputs=InputManifest(resource_ids=ids, evidence_revisions={rid:1 for rid in ids}), findings=['The image is sustained.', 'No sequence is inferred between unsampled moments.', 'The two references retain separate source identities.'], differences=['Authored comparison detail.'], opportunities=['Explore an abstract visual direction.'], limitations=['Authored fixture only; speech remains incomplete.'], sources=sources, structures=structures)
        state.analyses = [Analysis(conclusion='Analysis A saved takeaway.', **common), Analysis(content_id=item.id, conclusion='Independent content result.', **common)]
        state.workspace = 'analysis'
    project = store.update(project.id, project.version, populate)
    print(project.model_dump_json())
else:
    project = store.get(sys.argv[3])
    def change(state):
        if mode == 'replace':
            current = next(a for a in reversed(state.analyses) if a.content_id is None)
            new = current.model_copy(deep=True)
            from backend.app.project_workspace.models import uid
            new.id = uid('analysis')
            new.conclusion = 'Analysis B replacement takeaway.'
            state.analyses.append(new)
        elif mode == 'fail':
            state.jobs.append(Job(kind='analyze', status='failed', error='The service is temporarily busy. Try again shortly.', progress='Failed'))
        elif mode == 'reference_only':
            state.briefs = []
    print(store.update(project.id, project.version, change).model_dump_json())
