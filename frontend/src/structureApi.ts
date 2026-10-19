import { request } from './api';
export interface StructureMoment { event_id: string; start_frame: number | null; end_frame: number | null; start_seconds: number; end_seconds: number; precision: 'sample' | 'interval' }
export interface StructureNode { id: string; label: string; explanation: string; kind: 'observation' | 'source_claim' | 'inference' | 'user_context'; event_ids: string[]; source_ids: string[]; context_ids: string[]; moments: StructureMoment[] }
export interface StructureEdge { id: string; from_node: string; to_node: string; relation: string; explanation: string }
export interface StructureMethod { id: string; title: string; explanation: string; node_ids: string[]; conditions: string[] }
export interface StructureGraph { title: string; summary: string; nodes: StructureNode[]; edges: StructureEdge[]; methods: StructureMethod[]; research_gaps: { id: string; question: string; why_it_matters: string }[] }
export interface StructureSource { id: string; title: string; url: string; claim: string; attribution: string; retrieved_at: string }
export interface StructureContext { id: string; node_id: string; text: string; created_at: string }
export interface StructureAnswer { id: string; node_id: string; question: string; answer: string; event_ids: string[]; source_ids: string[]; created_at: string }
export interface StructureProposal { id: string; reason: string; graph: StructureGraph; sources: StructureSource[]; affected_node_ids: string[]; base_graph_revision: number; status: 'pending' | 'adopted' | 'superseded'; created_at: string }
export interface StructureState { output_language?: 'English' | 'Chinese' | null; structure_id: string; task_id: string; video_id: string; analysis_ref: { id: string; revision: number }; version: number; graph_revision: number; status: 'analyzing' | 'researching' | 'ready' | 'partial' | 'failed'; origin: 'sample' | 'provider'; graph: StructureGraph | null; sources: StructureSource[]; contexts: StructureContext[]; proposals: StructureProposal[]; answers: StructureAnswer[]; feedback_status: 'idle' | 'running' | 'failed'; error: { code: string; message: string } | null; research_note: string | null; outdated: boolean; source_deleted: boolean; created_at: string; updated_at: string }
export interface StructureHandoff { handoff_id: string; task_id: string; structure_id: string; structure_version: number; analysis_ref: { id: string; revision: number }; video_id: string; title: string; nodes: StructureNode[]; edges: StructureEdge[]; methods: StructureMethod[]; sources: StructureSource[]; contexts: StructureContext[]; created_at: string; note: string }
export const structureApi = {
  get: (task: string) => request<StructureState | null>(`/tasks/${task}/structure`),
  analyze: (task: string, analysis_ref: { id: string; revision: number }) => request<StructureState>(`/tasks/${task}/structure/analyze`, { analysis_ref }),
  feedback: (task: string, expected_version: number, node_id: string, instruction: string, kind: 'question' | 'context' | 'reconsider') => request<StructureState>(`/tasks/${task}/structure/feedback`, { expected_version, node_id, instruction, kind }),
  adopt: (task: string, expected_version: number, proposal: string) => request<StructureState>(`/tasks/${task}/structure/proposals/${proposal}/adopt`, { expected_version }),
  handoff: (task: string, expected_version: number, node_ids: string[], method_ids: string[], all: boolean) => request<StructureHandoff>(`/tasks/${task}/structure/handoff`, { expected_version, node_ids, method_ids, all }),
  getHandoff: (task: string) => request<StructureHandoff | null>(`/tasks/${task}/structure/handoff`),
};
