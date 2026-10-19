# Application language and interface localization

- Branch: `feat/workspace/structure-agent-redesign`.
- Starting revision: `70c08b08c3a48b5e9d94c773a5d349926f2a3f5b`.
- Environment: managed Linux workspace; changes shared with the integration team.

## Scope

The application defaults to English and offers a Chinese interface. The local
server preference is authoritative: `GET/POST /api/local/preferences` stores the
application language and research output language together. Only development
servers that return 404/405 may use a browser-local UI preference. Failed saves
leave the previous language active. A late startup read cannot overwrite a newer
explicit choice. The document language follows the active preference.

`frontend/src/i18n.tsx` supplies `I18nProvider`, `useI18n`, and a shared
`registerTranslations` registry. UI components use English source keys with
optional named substitutions. `i18nCatalog.ts` covers context inputs, proposals,
Ideas, Production, API connection, content-region editing, structured visual
corrections and shared form labels. Research and project-shell dictionaries are
owned by their corresponding modules.

Only authored interface strings and known application errors are localized.
Project names, typed drafts, product claims, saved model outputs, OCR quotes and
speech transcripts retain their original contents. Switching the interface does
not generate content, rewrite evidence, change approval state, or alter the
independent Ideas generation language. New research uses the server preference;
old saved results retain their recorded output language and can be regenerated
through an explicit action. This is interface localization, not model training.

## Validation

- TypeScript and ESLint: passed after integration of the preference and budget UI.
- Existing frontend unit files: seven passed.
- Three locale browser scenarios passed: cross-module language switching with
  authored-content and Ideas-language preservation, preference-save failure, and
  stale startup responses. Switching language made no generation requests.
- Four Directions, two Production and five API-connection browser scenarios also
  passed. The initial combined run passed 11 of 14; two API fixtures needed the
  new budget endpoint and removed-banner update, and a new Chinese selector
  needed to target the textbox rather than its identically named region. The
  three affected scenarios passed on rerun; no failed assertion was removed.
- No paid API requests, macOS execution, signing or deployment were performed by
  this workstream.

## Files

Main changes: `frontend/src/i18n.tsx`, `i18nCatalog.ts`, `main.tsx`, `ui.tsx`,
`Directions.tsx`, `Production.tsx`, `BriefEditor.tsx`, `M2Proposals.tsx`,
`ContentAreaEditor.tsx`, `VisualDetailsEditor.tsx`, `ApiConnection.tsx`, and
`frontend/e2e/locale.spec.ts`. The API connection dialog also mounts the separately
implemented budget controls while open. Installer and package prose remains in
English as requested.
