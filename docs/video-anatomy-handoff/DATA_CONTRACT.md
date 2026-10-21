# Video Anatomy data contract

Current baseline: v0.3.0, observed on 16 October 2026. Proposed next-version extensions follow the complete baseline field catalog. Current fields are implemented in the observed source; proposed additions are not.
## Shared rules

- Existing IDs match `^[A-Za-z][A-Za-z0-9_-]{1,63}$`; they are not translated labels.
- Source event/segment intervals use strict integer `[start_frame,end_frame)`, zero-based, bounded by frame_count. Actual source frame boundaries and media_start_seconds drive playback. Storyboard times are independent planned seconds.
- JSON null, zero, empty arrays, none_found, not_analyzed and failed have different meanings. Unknown values are not filled with invented observations.
- Events may overlap; primary segments are ordered and nonoverlapping. Citations name the exact analysis revision, event and video, with interval overlap.
- Current constructors can have defaults even when generated serialization schemas require those fields in full output. The Input column below describes construction, not permission to omit response keys.
- Extra fields are rejected by the current models. Current v0.3 has no visual_details, language, confidence, bounding_box or playback representation field.
- The source model snapshot contains all cross-field/aggregate validation. JSON Schema cannot by itself capture all reference/replay and workflow semantics.

## Complete current field catalog

### Record
| Field | Type | Unit | Input / null | Definition |
| --- | --- | --- | --- | --- |
| schema_version | string | none | Default "0.3.0"; not nullable | Version of the data format, distinct from an analysis revision. |
| created_at | datetime string | UTC datetime | Generated current UTC time; not nullable | Creation time of this record, timezone-aware and normalized to UTC. |
| updated_at | datetime string | UTC datetime | Generated current UTC time; not nullable | Latest update time; not earlier than creation. |

### VideoAsset
| Field | Type | Unit | Input / null | Definition |
| --- | --- | --- | --- | --- |
| schema_version | string | none | Default "0.3.0"; not nullable | Version of the data format, distinct from an analysis revision. Inherited from Record. |
| created_at | datetime string | UTC datetime | Generated current UTC time; not nullable | Creation time of this record, timezone-aware and normalized to UTC. Inherited from Record. |
| updated_at | datetime string | UTC datetime | Generated current UTC time; not nullable | Latest update time; not earlier than creation. Inherited from Record. |
| video_id | string | none | Required; not nullable | Stable reference/draft video identifier, not its filename. |
| task_id | string | none | Required; not nullable | Identifier of the owning creative task. |
| purpose | string | none | Default "reference"; not nullable | Whether this asset is a reference or a user draft. |
| input_method | string | none | Required; not nullable | How the stored asset entered the system; a source URL alone does not implement link import. |
| storage_id | string \| null | none | Default null; nullable | Safe local media-store key for the original saved asset. |
| content_sha256 | string \| null | none | Default null; nullable | SHA-256 of the stored original bytes when known. |
| sample_key | string \| null | none | Default null; nullable | Identifier of a dedicated sample; not proof that arbitrary media matches it. |
| original_file_name | string \| null | none | Default null; nullable | User-facing original filename; not a trusted filesystem path. |
| source_url | string \| null | none | Default null; nullable | Reference provenance URL; not an automatic downloader. |
| duration_seconds | number \| null | seconds (s) | Default null; nullable | Measured source-video duration, not the planned output length. |
| frame_timing | FrameTiming \| null | none | Default null; nullable | Measured source presentation-frame clock, or null when unavailable. |
| width | integer \| null | pixels | Default null; nullable | Source frame width. |
| height | integer \| null | pixels | Default null; nullable | Source frame height. |
| video_codec | string \| null | none | Default null; nullable | Actual original video codec; the intake code separately defines supported codecs. |
| audio_codec | string \| null | none | Default null; nullable | Original audio codec if known; null for unavailable/no audio. |
| has_audio | boolean \| null | none | Default null; nullable | Whether an audio stream exists; not a statement that speech was analyzed. |
| intake_status | string | none | Required; not nullable | Whether the media is ready, failed intake, or missing. |
| origin | Origin | none | Required; not nullable | Source classification and description for the record. |
| public_metrics | PublicMetrics \| null | none | Default null; nullable | Available public metric snapshot, tied to the same source URL. |
| error | ErrorInfo \| null | none | Default null; nullable | Actionable error information according to the enclosing status rules. |

### FrameTiming
| Field | Type | Unit | Input / null | Definition |
| --- | --- | --- | --- | --- |
| fps_numerator | integer | rational FPS numerator | Required; not nullable | Numerator of the nominal rational display frame rate; not a replacement for actual frame timestamps. |
| fps_denominator | integer | rational FPS denominator | Required; not nullable | Positive denominator of the nominal rational display frame rate. |
| frame_count | integer | frames | Required; not nullable | Number of decoded presentation-order source frames. |
| media_start_seconds | number | seconds (s) | Default 0.0; not nullable | Signed timestamp of the first frame on the media playback clock. |
| frame_boundaries_seconds | array<number> | seconds per array entry | Required; not nullable | Strictly increasing zero-relative frame boundaries; length is frame_count plus one, ending at measured duration. |
| rate_mode | string | none | Required; not nullable | Whether the measured source cadence is constant or variable. |
| source | string | none | Default "probed"; not nullable | The baseline value probed means measured from source media. |

### PublicMetrics
| Field | Type | Unit | Input / null | Definition |
| --- | --- | --- | --- | --- |
| source_url | string | none | Required; not nullable | Reference provenance URL; not an automatic downloader. |
| captured_at | datetime string \| null | UTC datetime | Default null; nullable | Time at which public metrics were captured, when known. |
| views | integer \| null | count | Default null; nullable | Observed public view count; unknown is null, not zero. |
| likes | integer \| null | count | Default null; nullable | Observed public like count; unknown is null, not zero. |
| comments | integer \| null | count | Default null; nullable | Observed public comment count; unknown is null, not zero. |

### Origin
| Field | Type | Unit | Input / null | Definition |
| --- | --- | --- | --- | --- |
| kind | string | none | Required; not nullable | Origin classification: sample, provider, manual or legacy. User correction does not relabel sample data as provider data. |
| description | string | none | Required; not nullable | Human-readable observation/source explanation; distinguish observation from interpretation. |

### ErrorInfo
| Field | Type | Unit | Input / null | Definition |
| --- | --- | --- | --- | --- |
| code | string | none | Required; not nullable | Stable error code suitable for programmatic handling. |
| message | string | none | Required; not nullable | Safe actionable error explanation. |
| retryable | boolean | none | Default false; not nullable | Whether retrying may resolve this failure. |

### ReferenceInterval
| Field | Type | Unit | Input / null | Definition |
| --- | --- | --- | --- | --- |
| start_frame | integer \| null | zero-based frame index | Default null; nullable | Inclusive zero-based index of the first source frame in the interval. |
| end_frame | integer \| null | exclusive frame boundary | Default null; nullable | Exclusive source-frame boundary; may equal frame_count. |
| legacy_seconds | LegacySeconds \| null | none | Default null; nullable | Preserved historical seconds when source timing cannot be recovered; cannot coexist with frame bounds. |

### LegacySeconds
| Field | Type | Unit | Input / null | Definition |
| --- | --- | --- | --- | --- |
| start_seconds | number | seconds (s) | Required; not nullable | Inclusive start in seconds; legacy source intervals and planned storyboard intervals belong to different clocks. |
| end_seconds | number | seconds (s) | Required; not nullable | End in seconds, strictly later than the start on the same clock. |

### EvidenceEvent
| Field | Type | Unit | Input / null | Definition |
| --- | --- | --- | --- | --- |
| start_frame | integer \| null | zero-based frame index | Default null; nullable | Inclusive zero-based index of the first source frame in the interval. Inherited from ReferenceInterval. |
| end_frame | integer \| null | exclusive frame boundary | Default null; nullable | Exclusive source-frame boundary; may equal frame_count. Inherited from ReferenceInterval. |
| legacy_seconds | LegacySeconds \| null | none | Default null; nullable | Preserved historical seconds when source timing cannot be recovered; cannot coexist with frame bounds. Inherited from ReferenceInterval. |
| event_id | string | none | Required; not nullable | Evidence-event identity within the versioned analysis; events have no independent revision field. |
| video_id | string | none | Required; not nullable | Stable reference/draft video identifier, not its filename. |
| lane | string | none | Required; not nullable | Visual or audio lane, determined by the event kind. |
| kind | string | none | Required; not nullable | Observation kind: visual_action, on_screen_text, speech, music or sfx. |
| text | string \| null | none | Default null; nullable | Recognized source words, preserved in their original language/script rather than rewritten creative copy. |
| description | string \| null | none | Default null; nullable | Description of visible/audible content; advertising claims are not independently verified facts. |
| source | string | none | Required; not nullable | How this observation or measured timing was obtained; inspect the enclosing type. |
| method | string | none | Required; not nullable | Description of the extraction method, such as OCR, transcription or manual annotation. |
| uncertainty | string \| null | none | Default null; nullable | Text describing ambiguity, blur, occlusion or other limitations; not a calibrated confidence score. |

### ContentSegment
| Field | Type | Unit | Input / null | Definition |
| --- | --- | --- | --- | --- |
| start_frame | integer \| null | zero-based frame index | Default null; nullable | Inclusive zero-based index of the first source frame in the interval. Inherited from ReferenceInterval. |
| end_frame | integer \| null | exclusive frame boundary | Default null; nullable | Exclusive source-frame boundary; may equal frame_count. Inherited from ReferenceInterval. |
| legacy_seconds | LegacySeconds \| null | none | Default null; nullable | Preserved historical seconds when source timing cannot be recovered; cannot coexist with frame bounds. Inherited from ReferenceInterval. |
| segment_id | string | none | Required; not nullable | Identity of a narrative content passage; not necessarily a physical shot boundary. |
| video_id | string | none | Required; not nullable | Stable reference/draft video identifier, not its filename. |
| roles | array<string> | none | Required; not nullable | One or more narrative roles; values are unique and other is exclusive. |
| evidence_ids | array<string> | none | Default []; not nullable | Referenced events from the same video whose intervals overlap the segment. |
| interpretation | string \| null | none | Default null; nullable | Explanation of narrative function, separate from observed evidence and causal proof. |

### Coverage
| Field | Type | Unit | Input / null | Definition |
| --- | --- | --- | --- | --- |
| visual_action | string | none | Default "not_analyzed"; not nullable | Coverage of visual observations; does not automatically establish coverage of each proposed nested group. |
| on_screen_text | string | none | Default "not_analyzed"; not nullable | Coverage of OCR evidence, or planned screen text when the enclosing object is a storyboard row. |
| speech | string | none | Default "not_analyzed"; not nullable | Coverage of speech transcription. |
| music | string | none | Default "not_analyzed"; not nullable | Coverage of music recognition. |
| sfx | string | none | Default "not_analyzed"; not nullable | Coverage of sound-effect/non-speech sound recognition. |

### AnalysisResult
| Field | Type | Unit | Input / null | Definition |
| --- | --- | --- | --- | --- |
| schema_version | string | none | Default "0.3.0"; not nullable | Version of the data format, distinct from an analysis revision. Inherited from Record. |
| created_at | datetime string | UTC datetime | Generated current UTC time; not nullable | Creation time of this record, timezone-aware and normalized to UTC. Inherited from Record. |
| updated_at | datetime string | UTC datetime | Generated current UTC time; not nullable | Latest update time; not earlier than creation. Inherited from Record. |
| analysis_id | string | none | Required; not nullable | Analysis identity; corrections retain it, while a fresh recognition run receives a new identity. |
| revision | integer | none | Default 1; not nullable | Positive revision number for the enclosing versioned record. |
| task_id | string | none | Required; not nullable | Identifier of the owning creative task. |
| video_id | string | none | Required; not nullable | Stable reference/draft video identifier, not its filename. |
| duration_seconds | number | seconds (s) | Required; not nullable | Measured source-video duration, not the planned output length. |
| frame_count | integer \| null | frames | Default null; nullable | Number of decoded presentation-order source frames. |
| status | string | none | Required; not nullable | Processing state of the enclosing type; inspect that type's allowed values and semantic validator. |
| events | array<EvidenceEvent> | none | Default []; not nullable | All evidence events, allowed to overlap in time and across lanes. |
| segments | array<ContentSegment> | none | Default []; not nullable | Ordered, nonoverlapping primary content segments; the baseline does not require full gapless coverage. |
| coverage | Coverage | none | Default Coverage(); not nullable | Separate completion/outcome states for the five evidence kinds. |
| origin | Origin | none | Required; not nullable | Source classification and description for the record. |
| original_revision | integer | none | Default 1; not nullable | Original extraction revision, fixed at one in the baseline. |
| review | ReviewState | none | Default ReviewState(); not nullable | Explicit user confirmation of this exact analysis revision. |
| corrections | array<Correction> | none | Default []; not nullable | Accumulated replayable before/after edits from original extraction to this revision. |
| error | ErrorInfo \| null | none | Default null; nullable | Actionable error information according to the enclosing status rules. |
| empty_result_reason | string \| null | none | Default null; nullable | Explanation for a completed analysis with no events; absent for nonempty results. |

### ReviewState
| Field | Type | Unit | Input / null | Definition |
| --- | --- | --- | --- | --- |
| user_confirmed | boolean | none | Default false; not nullable | Whether the user explicitly confirmed the current analysis revision. |
| confirmed_at | datetime string \| null | UTC datetime | Default null; nullable | Confirmation time; present exactly when user_confirmed is true. |

### Correction
| Field | Type | Unit | Input / null | Definition |
| --- | --- | --- | --- | --- |
| target_type | string | none | Required; not nullable | Whether a correction addresses an event or segment. |
| target_id | string | none | Required; not nullable | Identity of the corrected event or segment. |
| field | string | none | Required; not nullable | Baseline v0.3 allows event text/description and segment roles only. The extension below adds event visual_details. |
| before | JsonValue | none | Required; nullable | Previous field value captured for replay/audit; must have a valid type for the field. |
| after | JsonValue | none | Required; nullable | New validated field value. |

### EvidenceReference
| Field | Type | Unit | Input / null | Definition |
| --- | --- | --- | --- | --- |
| analysis_id | string | none | Required; not nullable | Analysis identity; corrections retain it, while a fresh recognition run receives a new identity. |
| analysis_revision | integer | none | Required; not nullable | Exact referenced analysis revision, not a floating latest pointer. |
| video_id | string | none | Required; not nullable | Stable reference/draft video identifier, not its filename. |
| event_id | string | none | Required; not nullable | Evidence-event identity within the versioned analysis; events have no independent revision field. |
| reason | string | none | Required; not nullable | Why a creative output cites this observation; not evidence of marketing effectiveness. |

### ProcessingJob
| Field | Type | Unit | Input / null | Definition |
| --- | --- | --- | --- | --- |
| schema_version | string | none | Default "0.3.0"; not nullable | Version of the data format, distinct from an analysis revision. Inherited from Record. |
| created_at | datetime string | UTC datetime | Generated current UTC time; not nullable | Creation time of this record, timezone-aware and normalized to UTC. Inherited from Record. |
| updated_at | datetime string | UTC datetime | Generated current UTC time; not nullable | Latest update time; not earlier than creation. Inherited from Record. |
| job_id | string | none | Required; not nullable | Processing operation identity, separate from analysis identity. |
| task_id | string | none | Required; not nullable | Identifier of the owning creative task. |
| operation | string | none | Required; not nullable | Analysis, direction generation, refinement or production generation. |
| status | string | none | Required; not nullable | Processing state of the enclosing type; inspect that type's allowed values and semantic validator. |
| input_refs | map<string, VersionRef> | none | Default {}; not nullable | Exact versioned inputs for this operation, using allowed reference keys. |
| video_id | string \| null | none | Default null; nullable | Stable reference/draft video identifier, not its filename. |
| result_ref | VersionRef \| null | none | Default null; nullable | Exact versioned result produced by a successful operation. |
| result_type | string \| null | none | Default null; nullable | Type of result; aggregate validation restricts the supported object kinds. |
| error | ErrorInfo \| null | none | Default null; nullable | Actionable error information according to the enclosing status rules. |
| attempt | integer | none | Default 1; not nullable | Positive attempt count; its existence does not imply a retry scheduler has run. |
| partial_coverage | boolean | none | Default false; not nullable | Whether partial coverage was recorded; this does not grant creative-generation eligibility. |

### VersionRef
| Field | Type | Unit | Input / null | Definition |
| --- | --- | --- | --- | --- |
| id | string | none | Required; not nullable | Identity portion of an exact VersionRef. |
| revision | integer | none | Required; not nullable | Positive revision number for the enclosing versioned record. |

### CreativeTask
| Field | Type | Unit | Input / null | Definition |
| --- | --- | --- | --- | --- |
| schema_version | string | none | Default "0.3.0"; not nullable | Version of the data format, distinct from an analysis revision. Inherited from Record. |
| created_at | datetime string | UTC datetime | Generated current UTC time; not nullable | Creation time of this record, timezone-aware and normalized to UTC. Inherited from Record. |
| updated_at | datetime string | UTC datetime | Generated current UTC time; not nullable | Latest update time; not earlier than creation. Inherited from Record. |
| task_id | string | none | Required; not nullable | Identifier of the owning creative task. |
| title | string | none | Required; not nullable | Human-readable task title. |
| mode | string | none | Default "real"; not nullable | Real or dedicated sample mode; never silently convert a real task to sample. |
| progress | string | none | Default "setup"; not nullable | Current product workflow stage. |
| version | integer | none | Default 1; not nullable | Task-wide optimistic concurrency version. |
| current_brief | VersionRef \| null | none | Default null; nullable | Exact current brand-brief revision. |
| current_video_id | string \| null | none | Default null; nullable | Current input video identity. |
| current_analysis | VersionRef \| null | none | Default null; nullable | Exact current analysis revision. |
| chosen_direction | VersionRef \| null | none | Default null; nullable | Approved/chosen direction reference under the existing workflow; not an unchecked UI selection. |
| selected_direction | VersionRef \| null | none | Default null; nullable | Current UI-selected direction reference; selection is not approval. |
| current_production_brief | VersionRef \| null | none | Default null; nullable | Exact current production-brief revision. |
| current_storyboard | VersionRef \| null | none | Default null; nullable | Exact current text-storyboard revision. |

### BrandTaskBrief
| Field | Type | Unit | Input / null | Definition |
| --- | --- | --- | --- | --- |
| schema_version | string | none | Default "0.3.0"; not nullable | Version of the data format, distinct from an analysis revision. Inherited from Record. |
| created_at | datetime string | UTC datetime | Generated current UTC time; not nullable | Creation time of this record, timezone-aware and normalized to UTC. Inherited from Record. |
| updated_at | datetime string | UTC datetime | Generated current UTC time; not nullable | Latest update time; not earlier than creation. Inherited from Record. |
| brief_id | string | none | Required; not nullable | Brand/task brief identity. |
| revision | integer | none | Default 1; not nullable | Positive revision number for the enclosing versioned record. |
| task_id | string | none | Required; not nullable | Identifier of the owning creative task. |
| brand_company | string | none | Required; not nullable | User's brand/company context for the new creative task. |
| product | string | none | Required; not nullable | User's product or service, distinct from a reference video's product. |
| selling_points | array<string> | none | Required; not nullable | Nonempty list of selling points supplied by the user. |
| approved_messages | array<string> | none | Default []; not nullable | Messages that may be used in creative output. |
| target_audience | string | none | Required; not nullable | Intended audience for the new video. |
| platform | string | none | Required; not nullable | Intended publishing platform. |
| communication_goal | string | none | Required; not nullable | Communication objective for the new video. |
| target_duration_seconds | number | seconds (s) | Required; not nullable | Planned new-video length, independent of the reference duration. |
| available_footage | string \| null | none | Default null; nullable | User-provided footage availability constraint. |
| presenters | string \| null | none | Default null; nullable | Available presenter/personnel constraint. |
| locations | string \| null | none | Default null; nullable | Available filming-location constraint. |
| tone | string \| null | none | Default null; nullable | Desired creative tone. |
| production_limits | string \| null | none | Default null; nullable | Production constraints such as resources, budget or practical limitations. |
| prohibited_claims | array<string> | none | Default []; not nullable | Claims the generated creative must avoid. |

### CreativeDirection
| Field | Type | Unit | Input / null | Definition |
| --- | --- | --- | --- | --- |
| schema_version | string | none | Default "0.3.0"; not nullable | Version of the data format, distinct from an analysis revision. Inherited from Record. |
| created_at | datetime string | UTC datetime | Generated current UTC time; not nullable | Creation time of this record, timezone-aware and normalized to UTC. Inherited from Record. |
| updated_at | datetime string | UTC datetime | Generated current UTC time; not nullable | Latest update time; not earlier than creation. Inherited from Record. |
| direction_id | string | none | Required; not nullable | Creative-direction identity. |
| revision | integer | none | Default 1; not nullable | Positive revision number for the enclosing versioned record. |
| task_id | string | none | Required; not nullable | Identifier of the owning creative task. |
| brief_ref | VersionRef | none | Required; not nullable | Exact brand-brief revision used to generate this output. |
| analysis_ref | VersionRef | none | Required; not nullable | Exact reviewed analysis revision used to generate this output. |
| feedback_refs | array<VersionRef> | none | Default []; not nullable | Exact user-feedback revisions used to produce this output. |
| core_message | string | none | Required; not nullable | Central message planned for the new video. |
| hook | string | none | Required; not nullable | Proposed new-video hook, distinct from a reference segment's hook role. |
| narrative | string | none | Required; not nullable | Proposed story direction/organization for the new video. |
| cta | string | none | Required; not nullable | Proposed call to action. |
| production_requirements | array<string> | none | Default []; not nullable | Resources or conditions required to make the proposed creative. |
| evidence | array<EvidenceReference> | none | Default []; not nullable | Precise citations to reference observations. |
| rationale | string | none | Required; not nullable | Reasons for the creative choice, separating observations from speculation. |
| hypotheses | array<string> | none | Default []; not nullable | Unverified creative hypotheses to test; not measured performance data. |
| production_notes | array<string> | none | Default []; not nullable | Practical production guidance. |
| origin | Origin | none | Required; not nullable | Source classification and description for the record. |
| approval_status | string | none | Default "draft"; not nullable | Draft or explicitly user-approved state. |
| approved_at | datetime string \| null | UTC datetime | Default null; nullable | Time of explicit approval of that exact direction revision. |
| currentness | string | none | Default "current"; not nullable | Whether an output matches current upstream inputs; outdated outputs are retained. |

### CreativeFeedback
| Field | Type | Unit | Input / null | Definition |
| --- | --- | --- | --- | --- |
| schema_version | string | none | Default "0.3.0"; not nullable | Version of the data format, distinct from an analysis revision. Inherited from Record. |
| created_at | datetime string | UTC datetime | Generated current UTC time; not nullable | Creation time of this record, timezone-aware and normalized to UTC. Inherited from Record. |
| updated_at | datetime string | UTC datetime | Generated current UTC time; not nullable | Latest update time; not earlier than creation. Inherited from Record. |
| feedback_id | string | none | Required; not nullable | User-feedback identity. |
| revision | integer | none | Default 1; not nullable | Positive revision number for the enclosing versioned record. |
| task_id | string | none | Required; not nullable | Identifier of the owning creative task. |
| instruction | string | none | Required; not nullable | Original user refinement instruction. |
| target_direction | VersionRef | none | Required; not nullable | Exact direction revision targeted by feedback. |
| brief_ref | VersionRef | none | Required; not nullable | Exact brand-brief revision used to generate this output. |
| analysis_ref | VersionRef | none | Required; not nullable | Exact reviewed analysis revision used to generate this output. |
| status | string | none | Default "pending"; not nullable | Processing state of the enclosing type; inspect that type's allowed values and semantic validator. |
| resulting_direction | VersionRef \| null | none | Default null; nullable | New direction revision actually produced when feedback is applied. |
| explanation | string \| null | none | Default null; nullable | Explanation of an uninterpreted instruction or other feedback outcome. |

### ProductionOutput
| Field | Type | Unit | Input / null | Definition |
| --- | --- | --- | --- | --- |
| schema_version | string | none | Default "0.3.0"; not nullable | Version of the data format, distinct from an analysis revision. Inherited from Record. |
| created_at | datetime string | UTC datetime | Generated current UTC time; not nullable | Creation time of this record, timezone-aware and normalized to UTC. Inherited from Record. |
| updated_at | datetime string | UTC datetime | Generated current UTC time; not nullable | Latest update time; not earlier than creation. Inherited from Record. |
| output_id | string | none | Required; not nullable | Production brief/storyboard identity. |
| revision | integer | none | Default 1; not nullable | Positive revision number for the enclosing versioned record. |
| task_id | string | none | Required; not nullable | Identifier of the owning creative task. |
| direction_ref | VersionRef | none | Required; not nullable | Exact approved direction revision used for production output. |
| brief_ref | VersionRef | none | Required; not nullable | Exact brand-brief revision used to generate this output. |
| analysis_ref | VersionRef | none | Required; not nullable | Exact reviewed analysis revision used to generate this output. |
| feedback_refs | array<VersionRef> | none | Default []; not nullable | Exact user-feedback revisions used to produce this output. |
| origin | Origin | none | Required; not nullable | Source classification and description for the record. |
| currentness | string | none | Default "current"; not nullable | Whether an output matches current upstream inputs; outdated outputs are retained. |
| edited | boolean | none | Default false; not nullable | Whether user editing has produced this output revision. |

### ProductionCreativeBrief
| Field | Type | Unit | Input / null | Definition |
| --- | --- | --- | --- | --- |
| schema_version | string | none | Default "0.3.0"; not nullable | Version of the data format, distinct from an analysis revision. Inherited from Record. |
| created_at | datetime string | UTC datetime | Generated current UTC time; not nullable | Creation time of this record, timezone-aware and normalized to UTC. Inherited from Record. |
| updated_at | datetime string | UTC datetime | Generated current UTC time; not nullable | Latest update time; not earlier than creation. Inherited from Record. |
| output_id | string | none | Required; not nullable | Production brief/storyboard identity. Inherited from ProductionOutput. |
| revision | integer | none | Default 1; not nullable | Positive revision number for the enclosing versioned record. Inherited from ProductionOutput. |
| task_id | string | none | Required; not nullable | Identifier of the owning creative task. Inherited from ProductionOutput. |
| direction_ref | VersionRef | none | Required; not nullable | Exact approved direction revision used for production output. Inherited from ProductionOutput. |
| brief_ref | VersionRef | none | Required; not nullable | Exact brand-brief revision used to generate this output. Inherited from ProductionOutput. |
| analysis_ref | VersionRef | none | Required; not nullable | Exact reviewed analysis revision used to generate this output. Inherited from ProductionOutput. |
| feedback_refs | array<VersionRef> | none | Default []; not nullable | Exact user-feedback revisions used to produce this output. Inherited from ProductionOutput. |
| origin | Origin | none | Required; not nullable | Source classification and description for the record. Inherited from ProductionOutput. |
| currentness | string | none | Default "current"; not nullable | Whether an output matches current upstream inputs; outdated outputs are retained. Inherited from ProductionOutput. |
| edited | boolean | none | Default false; not nullable | Whether user editing has produced this output revision. Inherited from ProductionOutput. |
| title | string | none | Required; not nullable | Human-readable task title. |
| core_message | string | none | Required; not nullable | Central message planned for the new video. |
| hook | string | none | Required; not nullable | Proposed new-video hook, distinct from a reference segment's hook role. |
| narrative | string | none | Required; not nullable | Proposed story direction/organization for the new video. |
| cta | string | none | Required; not nullable | Proposed call to action. |
| production_notes | array<string> | none | Default []; not nullable | Practical production guidance. |
| evidence | array<EvidenceReference> | none | Default []; not nullable | Precise citations to reference observations. |

### StoryboardRow
| Field | Type | Unit | Input / null | Definition |
| --- | --- | --- | --- | --- |
| row_id | string | none | Required; not nullable | Identity of a text-storyboard row. |
| start_seconds | number | seconds (s) | Required; not nullable | Inclusive start in seconds; legacy source intervals and planned storyboard intervals belong to different clocks. |
| end_seconds | number | seconds (s) | Required; not nullable | End in seconds, strictly later than the start on the same clock. |
| visual | string | none | Required; not nullable | Planned new-video visual content, not recognized reference footage. |
| dialogue | string \| null | none | Default null; nullable | Planned dialogue or narration for the new video. |
| on_screen_text | string \| null | none | Default null; nullable | Planned text appearing on screen in the new video. |
| sound | string \| null | none | Default null; nullable | Planned sound design for the new video. |
| cta | string \| null | none | Default null; nullable | Proposed call to action. |
| evidence | array<EvidenceReference> | none | Default []; not nullable | Precise citations to reference observations. |

### TextStoryboard
| Field | Type | Unit | Input / null | Definition |
| --- | --- | --- | --- | --- |
| schema_version | string | none | Default "0.3.0"; not nullable | Version of the data format, distinct from an analysis revision. Inherited from Record. |
| created_at | datetime string | UTC datetime | Generated current UTC time; not nullable | Creation time of this record, timezone-aware and normalized to UTC. Inherited from Record. |
| updated_at | datetime string | UTC datetime | Generated current UTC time; not nullable | Latest update time; not earlier than creation. Inherited from Record. |
| output_id | string | none | Required; not nullable | Production brief/storyboard identity. Inherited from ProductionOutput. |
| revision | integer | none | Default 1; not nullable | Positive revision number for the enclosing versioned record. Inherited from ProductionOutput. |
| task_id | string | none | Required; not nullable | Identifier of the owning creative task. Inherited from ProductionOutput. |
| direction_ref | VersionRef | none | Required; not nullable | Exact approved direction revision used for production output. Inherited from ProductionOutput. |
| brief_ref | VersionRef | none | Required; not nullable | Exact brand-brief revision used to generate this output. Inherited from ProductionOutput. |
| analysis_ref | VersionRef | none | Required; not nullable | Exact reviewed analysis revision used to generate this output. Inherited from ProductionOutput. |
| feedback_refs | array<VersionRef> | none | Default []; not nullable | Exact user-feedback revisions used to produce this output. Inherited from ProductionOutput. |
| origin | Origin | none | Required; not nullable | Source classification and description for the record. Inherited from ProductionOutput. |
| currentness | string | none | Default "current"; not nullable | Whether an output matches current upstream inputs; outdated outputs are retained. Inherited from ProductionOutput. |
| edited | boolean | none | Default false; not nullable | Whether user editing has produced this output revision. Inherited from ProductionOutput. |
| target_duration_seconds | number | seconds (s) | Required; not nullable | Planned new-video length, independent of the reference duration. |
| rows | array<StoryboardRow> | none | Required; not nullable | Time-ordered storyboard rows. |

### TaskState
| Field | Type | Unit | Input / null | Definition |
| --- | --- | --- | --- | --- |
| task | CreativeTask | none | Required; not nullable | Task master record and its current references. |
| briefs | array<BrandTaskBrief> | none | Default []; not nullable | Stored brand-brief revisions for this task. |
| videos | array<VideoAsset> | none | Default []; not nullable | Stored video assets for this task. |
| analyses | array<AnalysisResult> | none | Default []; not nullable | Stored analysis and correction revisions for this task. |
| directions | array<CreativeDirection> | none | Default []; not nullable | Stored creative-direction revisions for this task. |
| feedback | array<CreativeFeedback> | none | Default []; not nullable | Stored user-feedback revisions for this task. |
| production_briefs | array<ProductionCreativeBrief> | none | Default []; not nullable | Stored production-brief revisions for this task. |
| storyboards | array<TextStoryboard> | none | Default []; not nullable | Stored text-storyboard revisions for this task. |
| jobs | array<ProcessingJob> | none | Default []; not nullable | Stored processing operations for this task. |

## Existing enum values

These are distinct taxonomies. An event kind, an entity kind and a narrative role are not interchangeable.

| Type | Values |
| --- | --- |
| EventKind | `visual_action`, `on_screen_text`, `speech`, `music`, `sfx` |
| Lane | `visual`, `audio` |
| Role | `hook`, `product_demo`, `proof`, `cta`, `other` |
| CoverageStatus | `not_analyzed`, `observations`, `none_found`, `failed` |
| OriginKind | `sample`, `provider`, `manual`, `legacy` |
| InputMethod | `file`, `sample`, `legacy` |
| VideoPurpose | `reference`, `draft` |
| IntakeStatus | `ready`, `failed`, `missing` |
| AnalysisStatus | `pending`, `running`, `succeeded`, `partial`, `failed` |
| JobStatus | `pending`, `running`, `succeeded`, `failed` |
| JobOperation | `analyze`, `directions`, `refine`, `production` |
| RateMode | `constant`, `variable` |
| CorrectionTarget | `event`, `segment` |
| TaskMode | `real`, `sample` |
| TaskProgress | `setup`, `analysis`, `review`, `directions`, `production` |
| FeedbackStatus | `pending`, `applied`, `not_interpreted` |
| Approval | `draft`, `approved` |
| Currentness | `current`, `outdated` |

## Key baseline state semantics

CoverageStatus: not_analyzed means the capability was not run; observations means events exist; none_found means it was checked and no observation was found; failed means attempted unsuccessfully. Top-level coverage must agree with canonical events. Current succeeded forbids failed coverage; current partial requires a failed coverage category. The next-version nested-failure extension below updates that relationship without discarding successful visual observations.

Analysis confirmation is explicit and revision-specific. Creative generation requires the current successful confirmed analysis with known source timing. Direction selection is not approval; production uses the exact approved direction. Edits preserve past outputs but mark dependent outputs outdated and clear dependent approval. Legacy unresolved timing cannot be treated as measured frames.

## Next contract: structured visual data

Implementation proposal: v0.4.0 if the live repository is still v0.3.0. The high-level three-group structure and user correction capability are confirmed. The following concrete names and category lists are the implementation baseline, not an assertion that every enum was separately approved. Preserve their meaning; document any necessary changes. Nothing in this section is accepted by the unmodified v0.3 API.

### Added fields

All nested visual items inherit the parent EvidenceEvent source-frame interval. They do not have independent timestamps, cross-shot track IDs or confidence scores.

| Object.field | Type / unit | Meaning and rule |
| --- | --- | --- |
| EvidenceEvent.visual_details | VisualDetails or null / none | Only permitted on kind=visual_action. Keep the original description. Legacy/unanalyzed structured content is null, not an empty detected scene. |
| VisualDetails.subjects | ObservationGroup of VisualSubject / none | Significant entities in this observation; not every visible object. |
| VisualDetails.actions | ObservationGroup of VisualAction / none | Observable actions and their local participant references. |
| VisualDetails.product_presentations | ObservationGroup of ProductPresentation / none | Ways an identified product is presented; not proof of effectiveness. |
| ObservationGroup.status | CoverageStatus / none | not_analyzed, observations, none_found or failed, independently for each group. |
| ObservationGroup.items | array of typed items / none | Nonempty exactly when status=observations; otherwise empty. |
| ObservationGroup.error | ErrorInfo or null / none | Required exactly for failed; otherwise null. |
| VisualSubject.subject_id | ID / none | Unique inside one event; address with analysis revision + event_id + subject_id. No cross-event identity guarantee. |
| VisualSubject.kind | SubjectKind or null / none | Single physical/representational entity kind. Unknown is JSON null. |
| VisualSubject.label | nonempty string / none | Short human-readable name based on observable appearance. |
| VisualSubject.description | nonempty string or null / none | Visible detail and classification explanation; required for an other kind or role. |
| VisualSubject.roles | nonempty unique array of SubjectRole or null / none | Roles in the reference; null means uncertain. Empty array and [null] are invalid. other must stand alone. |
| VisualAction.action_type | ActionType or null / none | One visible action category; preserve description even when unknown. |
| VisualAction.actor_subject_ids | unique array of ID / none | References to this event's subjects performing the action. Empty if no actor can be linked; explain why. |
| VisualAction.target_subject_ids | unique array of ID / none | References to this event's affected subjects. Empty if no target can be linked; explain why rather than asserting no target exists. |
| VisualAction.description | nonempty string / none | Specific observed action, without inferred intent or efficacy. |
| ProductPresentation.product_subject_ids | nonempty unique array of ID / none | References to local subjects whose roles include product. |
| ProductPresentation.presentation_type | ProductPresentationType or null / none | One method per item; several items may describe the same product. |
| ProductPresentation.description | nonempty string / none | Observed presentation; source advertising claims belong in text events. |

### SubjectKind: what an entity is

| Code | Definition |
| --- | --- |
| person | A visible person or recognizable representation of one; do not infer identity or demographics. |
| animal | An animal as the relevant visible entity. |
| plant | A plant as the relevant visible entity; it can separately have product role. |
| physical_object | A physical object, including products, packaging and tools. |
| digital_interface | An app, website or other interactive interface shown on screen. |
| graphic | A diagram, icon, illustration, chart or graphic element treated as an entity. |
| environment | A meaningful location, setting or surrounding environment. |
| other | A positively observed entity outside these kinds; explain in description. |

JSON null means unknown; it is not an enum code. A product is normally a role, not an entity kind. An advertised app can be kind=digital_interface and roles=[product]. Background setting and the main product are not forced into one mutually exclusive label.

### SubjectRole: what an entity does in the reference

| Code | Definition |
| --- | --- |
| product | The item/service/interface being shown or promoted in the reference; not automatically the user's own brand. |
| presenter | The entity visibly presenting or explaining the content. |
| product_user | An entity visibly using the product. |
| context | Supporting/background context relevant to the observation. |
| other | A known role outside the list; exclusive and explained. |

Roles are multilabel. For example, a person may be both presenter and product_user. null means uncertain; other does not mean uncertain.

### ActionType: visible actions

| Code | Definition |
| --- | --- |
| hold | Hold or support an object. |
| pick_up | Lift an object from its previous support. |
| put_down | Place an object onto a support. |
| open | Open a container, lid, door or comparable item. |
| close | Close a container, lid, door or comparable item. |
| pour | Transfer a flowing substance by pouring. |
| apply | Apply/spread a product or substance to a surface/body. |
| operate | Use a control, device or interface. |
| assemble | Join components together. |
| disassemble | Separate joined components. |
| wear | Put on or visibly wear an item. |
| eat_drink | Consume food or drink. |
| point | Point or gesture toward something. |
| move | Relevant visible movement not better described above. |
| other | Another observed action; describe it. |

Use one category per action item. Static product visibility does not require an invented action; its actions group may be none_found after analysis.

### ProductPresentationType: how the product is shown

| Code | Definition |
| --- | --- |
| appearance | Product shape, surface, color or visible details. |
| feature_demo | A visible feature or operating process is demonstrated. |
| use_case | Product use in a concrete situation. |
| result_display | An outcome is displayed or claimed; not independently verified causation. |
| comparison | A comparison is visibly presented. |
| packaging | Product packaging is shown. |
| unboxing | Removal/unpacking from packaging is shown. |
| other | Another presentation method; explain it. |

### Semantic validation beyond JSON Schema

- All three groups are present when visual_details is non-null. Cross-group status must not be inferred from the parent's Coverage.visual_action value.
- Local subject IDs are unique. All nonempty actor/target/product references resolve within the same event. Product references require a product role.
- No duplicate roles or relationship references. other is exclusive for multilabel role fields.
- Only visual_action events can have non-null visual_details. Child time units are inherited source frames.
- A failed structured group retains its ErrorInfo and makes the analysis partial under the proposed conservative default. Extend the current partial-state validator to accept nested group failure as a reason; keep successfully observed parent events and their truthful top-level coverage.
- An unknown label with a description is not an extraction failure. not_analyzed is not none_found. An unavailable feature must not be represented as a confident negative.
- Existing downstream rules still require succeeded + explicit review of the exact current revision. No automatic approval.
- The JSON Schema in schemas/proposed/visual-details.schema.json validates shapes and local status relationships; the implementation must also validate event kind, local references, role dependencies and analysis state.

## Next contract: editable structured labels

Extend Correction.field with visual_details for target_type=event. before and after are the full validated VisualDetails value, captured server-side. Preserve the previous text/description and segment-role correction rules.

Allowed leaf changes in this first implementation:

| Location | Editable |
| --- | --- |
| subjects.items | kind, roles, label, description |
| actions.items | action_type, description |
| product_presentations.items | presentation_type, description |

IDs, array size/order, relationship references, status/error fields and time intervals remain immutable through this correction path. A whole-object payload is not permission to replace arbitrary content. Validate the new object and the allowlisted differences before committing. Reject stale revision writes and changes that leave product references inconsistent.

Corrections append an analysis revision, preserve original_revision=1 and clear the current review. Existing downstream invalidation must preserve old outputs while marking them outdated and clearing dependent approval. A complete re-analysis receives a new analysis_id; correction does not.

## Next contract: playback representation

Original source metadata remains authoritative. For browser-compatible HEVC playback, propose an additional VideoAsset.playback value:

| Field | Type / unit | Meaning |
| --- | --- | --- |
| VideoAsset.playback | PlaybackRepresentation or null / none | Optional derived playback asset; null means use the original playable asset. |
| PlaybackRepresentation.storage_id | validated storage ID / none | Stored H.264 MP4 derivative, following the repository's safe storage-key rules. |
| PlaybackRepresentation.video_codec | literal h264 / none | Codec of the derived playback file only. |
| PlaybackRepresentation.audio_codec | literal aac or null / none | Codec of the derivative's audio, or null when no audio is present. |
| PlaybackRepresentation.duration_seconds | positive finite number / seconds | Measured derivative duration. |
| PlaybackRepresentation.frame_timing | FrameTiming / source-indexed presentation frames | Measured derivative timing; frame_count equals the original count, with one-to-one presentation-order correspondence validated by the pipeline. |

Use playback.frame_timing when seeking the derivative, and original frame_timing for original-source recognition. Preserve source event frame indices. Do not replace the source timing/codec/hash with derivative values. If frame order/count correspondence cannot be established, fail the conversion explicitly. If the live code already has an equivalent safe representation, reuse it and document the mapping rather than adding a duplicate.

## Bilingual contract rules

Text values support Unicode. OCR and ASR text preserves the original English, Chinese or mixed-language content. Explanatory prose and generated creative language are separate configuration concerns. Machine keys, IDs and enum codes stay unchanged. Do not add language/confidence fields to v0.3 records without a versioned change; this mission does not require speculative per-token language metadata.

## Compatibility and migration

Old records migrate to visual_details=null and playback=null without fabricating extraction or a proxy. Preserve old correction replay and source citations. Version the canonical model, regenerate types/schemas, and keep historic schemas. A schema-only migration is not a new recognition run or fresh user confirmation. Check actual current models before choosing a version. The current snapshots bundled here are documentation/test references only.
