import type { M2EditorStatus } from './BriefEditor';
import type { TaskState } from './generated/contracts';

export type ProductionDestination = 'context' | 'ideas' | 'timeline';
export type ProductionBlocker = { message: string; action?: string; destination?: ProductionDestination };

/** Explain the next actionable prerequisite without hiding previously saved work. */
export function productionBlocker(state: TaskState, context: M2EditorStatus, analysisPending: boolean, directionPending: boolean): ProductionBlocker | null {
  if (context.error) return { message: context.loading ? 'Project context could not be loaded.' : 'Project context changes could not be saved.', action: 'Review project context', destination: 'context' };
  if (context.loading) return { message: 'Loading project context…' };
  if (context.unsaved) return { message: 'Project context has unsaved changes.', action: 'Review project context', destination: 'context' };
  if (context.legacyReviewRequired) return { message: 'Review product claims before generating.', action: 'Review product claims', destination: 'context' };
  const brief = state.briefs.find((item) => item.brief_id === state.task.current_brief?.id && item.revision === state.task.current_brief.revision);
  if (!brief || (context.pending && context.missing.length > 0)) return { message: 'Complete project context before generating.', action: 'Complete project context', destination: 'context' };
  if (context.pending) return { message: 'Project context changes need to be applied.', action: 'Apply context changes', destination: 'context' };
  if (!state.task.generation_language) return { message: 'Choose a generation language in Ideas.', action: 'Choose generation language', destination: 'ideas' };
  if (directionPending) return { message: 'Resolve the selected idea draft before generating.', action: 'Review idea draft', destination: 'ideas' };
  const direction = state.directions.find((item) => item.direction_id === state.task.selected_direction?.id && item.revision === state.task.selected_direction.revision);
  if (!direction || direction.approval_status !== 'approved' || direction.currentness !== 'current' || direction.brief_ref.id !== brief.brief_id || direction.brief_ref.revision !== brief.revision) return { message: 'Approve a current idea before generating.', action: 'Choose and approve an idea', destination: 'ideas' };
  // Original ideas never inherit a prerequisite from unrelated reference work.
  if (direction.analysis_ref) {
    if (analysisPending) return { message: 'Save or discard reference corrections before generating.', action: 'Review timeline corrections', destination: 'timeline' };
    const reference = direction.analysis_ref;
    const analysis = state.analyses.find((item) => item.analysis_id === reference.id && item.revision === reference.revision);
    if (reference.id !== state.task.current_analysis?.id || reference.revision !== state.task.current_analysis.revision || !analysis || analysis.video_id !== state.task.current_video_id) return { message: 'The approved idea uses an earlier reference.', action: 'Review and approve an idea', destination: 'ideas' };
    if (analysis.status !== 'succeeded' || analysis.frame_count == null) return { message: 'Complete the reference analysis before generating.', action: 'Review reference analysis', destination: 'timeline' };
    if (!analysis.review.user_confirmed) return { message: 'Confirm the reference analysis before generating.', action: 'Review reference analysis', destination: 'timeline' };
  }
  return null;
}
