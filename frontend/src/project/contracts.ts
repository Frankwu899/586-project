/* Generated from contracts/v1.8.project.schema.json. Do not edit. */

export type SchemaVersion = "1.8.0";
export type Id = string;
export type Title = string;
export type Version = number;
export type CreatedAt = string;
export type UpdatedAt = string;
export type TrashedAt = string | null;
export type DuplicatedFrom = string | null;
export type LegacyTaskId = string | null;
export type Workspace = string;
export type ActiveContentId = string | null;
export type ConversationDraft = string;
export type Id1 = string;
export type Role = "user" | "assistant" | "system";
export type Text = string;
export type ResourceIds = string[];
export type CreatedAt1 = string;
export type Status = "saved" | "failed";
export type ReplyToMessageId = string | null;
export type Retryable = boolean;
export type Messages = Message[];
export type Id2 = string;
export type Key = string;
export type Value = string;
export type Status1 = "suggested" | "confirmed" | "unresolved" | "rejected";
export type Origin = "conversation" | "document" | "research" | "manual" | "legacy";
export type ResourceId = string | null;
export type MessageId = string | null;
export type Locator = string;
export type Excerpt = string;
export type Url = string | null;
export type EvidenceRevision = number | null;
export type ExtractionRevision = number | null;
export type EventId = string | null;
export type StartSeconds = number | null;
export type EndSeconds = number | null;
export type Sources = SourceRef[];
export type PermittedForUse = boolean;
export type BriefDraft = Fact[];
export type BriefDraftVersion = number;
export type Unresolved = string[];
export type Revision = number;
export type Facts = Fact[];
export type CreatedAt2 = string;
export type Briefs = BriefRevision[];
export type Id3 = string;
export type Name = string;
export type Kind = "document" | "video" | "audio" | "image" | "other";
export type Role1 = "reference" | "document" | "asset";
export type Origin1 = "upload" | "discovery" | "legacy";
export type SourceUrl = string | null;
export type Provenance = string;
export type OriginalPath = string;
export type Sha256 = string;
export type SizeBytes = number;
export type MimeType = string;
export type CreatedAt3 = string;
export type Status2 = "stored" | "processing" | "ready" | "partial" | "failed" | "unsupported" | "missing";
export type Error = string | null;
export type Warnings = string[];
export type Id4 = string;
export type Locator1 = string;
export type Text1 = string;
export type OriginalText = string | null;
export type Blocks = ExtractedBlock[];
export type ExtractionRevision1 = number;
export type ExtractionHistory = {
  [k: string]: unknown;
}[];
export type DurationSeconds = number | null;
export type ThumbnailPath = string | null;
export type PlaybackPath = string | null;
export type SupportDetails = {
  [k: string]: string;
}[];
export type Revision1 = number;
export type Id5 = string;
export type Kind1 = "speech" | "on_screen_text" | "visual" | "sound";
export type Text2 = string;
export type StartSeconds1 = number;
export type EndSeconds1 = number;
export type StartFrame = number | null;
export type EndFrame = number | null;
export type Interpretation = string | null;
export type Events = EvidenceEvent[];
export type Limitations = string[];
export type Processor = string;
export type CreatedAt4 = string;
export type Reviewed = boolean;
export type CorrectionNote = string | null;
export type Evidence = EvidenceRevision1[];
export type Resources = Resource[];
export type Revision2 = number;
export type ResourceIds1 = string[];
export type Id6 = string;
export type ContentId = string | null;
export type Exploratory = boolean;
export type VisualOnly = boolean;
export type Limitations1 = string[];
export type BriefRevision1 = number | null;
export type SelectionRevision = number;
export type ResourceIds2 = string[];
export type DirectionId = string | null;
export type DirectionRevision = number | null;
export type InstructionVersion = string;
export type InstructionDigest = string | null;
export type ContextDigest = string | null;
export type ClaimIds = string[];
export type Model = string | null;
export type Conclusion = string;
export type Findings = string[];
export type Differences = string[];
export type Opportunities = string[];
export type Sources1 = SourceRef[];
export type Limitations2 = string[];
export type ResourceId1 = string;
export type Summary = string;
export type Id7 = string;
export type Label = string;
export type Detail = string;
export type Kind2 = "observation" | "interpretation" | "source_claim" | "user_context";
export type Sources2 = SourceRef[];
export type Nodes = StructureNode[];
export type Source = string;
export type Target = string;
export type Label1 = string;
export type Explanation = string;
export type Sources3 = SourceRef[];
export type Edges = StructureEdge[];
export type Structures = ReferenceStructure[];
export type CreatedAt5 = string;
export type NeedsReview = boolean;
export type Analyses = Analysis[];
export type Id8 = string;
export type Title1 = string;
export type Concept = string;
export type NeedsReview1 = boolean;
export type Series = Series1[];
export type Id9 = string;
export type SeriesId = string | null;
export type Title2 = string;
export type Description = string;
export type NeedsReview2 = boolean;
export type Id10 = string;
export type Revision3 = number;
export type Title3 = string;
export type Concept1 = string;
export type Hook = string;
export type Narrative = string;
export type Cta = string;
export type Sources4 = SourceRef[];
export type Approved = boolean;
export type ApprovedAt = string | null;
export type NeedsReview3 = boolean;
export type CreatedAt6 = string;
export type Directions = Direction[];
export type ApprovedDirectionId = string | null;
export type ApprovedDirectionRevision = number | null;
export type Contents = ContentItem[];
export type Id11 = string;
export type Revision4 = number;
export type ContentId1 = string;
export type ProductionBrief = string;
export type Script = string;
export type Storyboard = string;
export type ShotList = string;
export type Id12 = string;
export type StartSeconds2 = number;
export type EndSeconds2 = number;
export type Visual = string;
export type Dialogue = string;
export type OnScreenText = string;
export type Sound = string;
export type Notes = string;
export type Shots = ProductionShot[];
export type Sources5 = SourceRef[];
export type NeedsReview4 = boolean;
export type CreatedAt7 = string;
export type Packs = ProductionPack[];
export type ErrorCode = string | null;
export type Id13 = string;
export type Kind3 = string;
export type ResourceId2 = string | null;
export type ContentId2 = string | null;
export type MessageId1 = string | null;
export type SupportDetails1 = {
  [k: string]: string;
}[];
export type Status3 = "queued" | "running" | "succeeded" | "partial" | "failed";
export type Progress = string;
export type Error1 = string | null;
export type CreatedAt8 = string;
export type UpdatedAt1 = string;
export type Jobs = Job[];

export interface Project {
  schema_version: SchemaVersion;
  id: Id;
  title: Title;
  version: Version;
  created_at: CreatedAt;
  updated_at: UpdatedAt;
  trashed_at: TrashedAt;
  duplicated_from: DuplicatedFrom;
  legacy_task_id: LegacyTaskId;
  workspace: Workspace;
  active_content_id: ActiveContentId;
  conversation_draft: ConversationDraft;
  messages: Messages;
  brief_draft: BriefDraft;
  brief_draft_version: BriefDraftVersion;
  unresolved: Unresolved;
  briefs: Briefs;
  resources: Resources;
  selection: Selection;
  analyses: Analyses;
  series: Series;
  contents: Contents;
  packs: Packs;
  jobs: Jobs;
  editor_drafts: EditorDrafts;
  editor_draft_versions: EditorDraftVersions;
}
export interface Message {
  id: Id1;
  role: Role;
  text: Text;
  resource_ids: ResourceIds;
  created_at: CreatedAt1;
  status: Status;
  reply_to_message_id: ReplyToMessageId;
  diagnostics: Diagnostics;
  retryable: Retryable;
}
export interface Diagnostics {
  [k: string]: string;
}
export interface Fact {
  id: Id2;
  key: Key;
  value: Value;
  status: Status1;
  origin: Origin;
  sources: Sources;
  permitted_for_use: PermittedForUse;
}
export interface SourceRef {
  resource_id: ResourceId;
  message_id: MessageId;
  locator: Locator;
  excerpt: Excerpt;
  url: Url;
  evidence_revision: EvidenceRevision;
  extraction_revision: ExtractionRevision;
  event_id: EventId;
  start_seconds: StartSeconds;
  end_seconds: EndSeconds;
}
export interface BriefRevision {
  revision: Revision;
  facts: Facts;
  created_at: CreatedAt2;
}
export interface Resource {
  id: Id3;
  name: Name;
  kind: Kind;
  role: Role1;
  origin: Origin1;
  source_url: SourceUrl;
  provenance: Provenance;
  original_path: OriginalPath;
  sha256: Sha256;
  size_bytes: SizeBytes;
  mime_type: MimeType;
  created_at: CreatedAt3;
  status: Status2;
  error: Error;
  warnings: Warnings;
  blocks: Blocks;
  extraction_revision: ExtractionRevision1;
  extraction_history: ExtractionHistory;
  duration_seconds: DurationSeconds;
  thumbnail_path: ThumbnailPath;
  playback_path: PlaybackPath;
  media_metadata: MediaMetadata;
  evidence: Evidence;
}
export interface ExtractedBlock {
  id: Id4;
  locator: Locator1;
  text: Text1;
  original_text: OriginalText;
}
export interface MediaMetadata {
  [k: string]: unknown;
}
export interface EvidenceRevision1 {
  diagnostics: Diagnostics1;
  support_details: SupportDetails;
  revision: Revision1;
  events: Events;
  coverage: Coverage;
  limitations: Limitations;
  processor: Processor;
  created_at: CreatedAt4;
  reviewed: Reviewed;
  correction_note: CorrectionNote;
}
export interface Diagnostics1 {
  [k: string]: string;
}
export interface EvidenceEvent {
  id: Id5;
  kind: Kind1;
  text: Text2;
  start_seconds: StartSeconds1;
  end_seconds: EndSeconds1;
  start_frame: StartFrame;
  end_frame: EndFrame;
  interpretation: Interpretation;
}
export interface Coverage {
  [k: string]: string;
}
export interface Selection {
  revision: Revision2;
  resource_ids: ResourceIds1;
}
export interface Analysis {
  id: Id6;
  content_id: ContentId;
  inputs: InputManifest;
  conclusion: Conclusion;
  findings: Findings;
  differences: Differences;
  opportunities: Opportunities;
  sources: Sources1;
  limitations: Limitations2;
  structures: Structures;
  created_at: CreatedAt5;
  needs_review: NeedsReview;
}
export interface InputManifest {
  exploratory: Exploratory;
  visual_only: VisualOnly;
  limitations: Limitations1;
  brief_revision: BriefRevision1;
  selection_revision: SelectionRevision;
  resource_ids: ResourceIds2;
  evidence_revisions: EvidenceRevisions;
  direction_id: DirectionId;
  direction_revision: DirectionRevision;
  instruction_version: InstructionVersion;
  instruction_digest: InstructionDigest;
  context_digest: ContextDigest;
  claim_ids: ClaimIds;
  model: Model;
}
export interface EvidenceRevisions {
  [k: string]: number;
}
export interface ReferenceStructure {
  resource_id: ResourceId1;
  summary: Summary;
  nodes: Nodes;
  edges: Edges;
}
export interface StructureNode {
  id: Id7;
  label: Label;
  detail: Detail;
  kind: Kind2;
  sources: Sources2;
}
export interface StructureEdge {
  source: Source;
  target: Target;
  label: Label1;
  explanation: Explanation;
  sources: Sources3;
}
export interface Series1 {
  id: Id8;
  title: Title1;
  concept: Concept;
  inputs: InputManifest | null;
  needs_review: NeedsReview1;
}
export interface ContentItem {
  id: Id9;
  series_id: SeriesId;
  title: Title2;
  description: Description;
  inputs: InputManifest | null;
  needs_review: NeedsReview2;
  selection: Selection;
  directions: Directions;
  approved_direction_id: ApprovedDirectionId;
  approved_direction_revision: ApprovedDirectionRevision;
}
export interface Direction {
  id: Id10;
  revision: Revision3;
  title: Title3;
  concept: Concept1;
  hook: Hook;
  narrative: Narrative;
  cta: Cta;
  inputs: InputManifest;
  sources: Sources4;
  approved: Approved;
  approved_at: ApprovedAt;
  needs_review: NeedsReview3;
  created_at: CreatedAt6;
}
export interface ProductionPack {
  id: Id11;
  revision: Revision4;
  content_id: ContentId1;
  inputs: InputManifest;
  production_brief: ProductionBrief;
  script: Script;
  storyboard: Storyboard;
  shot_list: ShotList;
  shots: Shots;
  sources: Sources5;
  needs_review: NeedsReview4;
  created_at: CreatedAt7;
}
export interface ProductionShot {
  id: Id12;
  start_seconds: StartSeconds2;
  end_seconds: EndSeconds2;
  visual: Visual;
  dialogue: Dialogue;
  on_screen_text: OnScreenText;
  sound: Sound;
  notes: Notes;
}
export interface Job {
  error_code: ErrorCode;
  id: Id13;
  kind: Kind3;
  resource_id: ResourceId2;
  content_id: ContentId2;
  message_id: MessageId1;
  diagnostics: Diagnostics2;
  support_details: SupportDetails1;
  status: Status3;
  progress: Progress;
  error: Error1;
  created_at: CreatedAt8;
  updated_at: UpdatedAt1;
}
export interface Diagnostics2 {
  [k: string]: string;
}
export interface EditorDrafts {
  [k: string]: {
    [k: string]: unknown;
  };
}
export interface EditorDraftVersions {
  [k: string]: number;
}
