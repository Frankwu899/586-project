---
name: grilling
description: Grill the user relentlessly about a plan, decision, or idea. Use when the user wants to stress-test their thinking, or uses any 'grill' trigger phrases.
---

Interview the user relentlessly until you reach a shared understanding. Map this as a **design tree**: every decision branches into the decisions that hang off it.

Work the tree in **rounds**. The **frontier** is every decision whose prerequisites are already settled: the questions you can ask _now_ without guessing at answers you haven't heard yet. Ask the whole frontier in one round: number each question and give your recommended answer. Then wait for the user's answers before the next round.

## Interactive question transport (owner customization)

The owner requires native interactive question boxes, never plain-text interview
questions. This replaces the upstream Markdown question/answer format.

- In Codex Default mode call `functions.request_user_input_async`. Use
  `functions.request_user_input` only when the active mode supports it.
- Put the complete, self-contained question, stable topic ID and necessary
  context in each question title. Use topic-specific IDs such as S1 for Structure
  so they cannot be confused with earlier project Q1-Q3.
- Include two or three mutually exclusive, concrete options where useful. Put
  the recommended option first and mark it Recommended (or the user's language
  equivalent). Explain material tradeoffs briefly in the question or options.
  Do not invent an Other option: the UI already supports free text.
- Keep each round manageable (normally one to three independent questions).
  Batch ready questions into the interactive UI; do not ask a dependent question
  before its prerequisite has been answered. Recompute the frontier after replies.
- Send questions only through that UI. Commentary may explain a finding or
  recommendation but must not contain another question. Do not duplicate the
  submitted questions in the final answer.
- A preselected recommendation, silence, elapsed time or an unanswered async
  request is not an answer. Keep decision-dependent work pending. Continue
  independent fact-finding where useful. Bind each reply to its question ID.
- If the interactive tool is unavailable, report the missing capability and
  keep the interview pending; do not quietly fall back to plain-text questions.
- Use Chinese for this owner's conversation and questions. Repository skill,
  handoff, installer and delivery documents remain English.
- Reuse established decisions, including Q1-Q3, without asking them again.
  Distinguish confirmed decisions, recommendations and open questions. If new
  feedback reopens an earlier rule, identify the changed issue explicitly.

Each round the user answers reshapes the tree: settled decisions push the frontier outward and unblock questions that depended on them. Recompute the frontier and ask the next round. A question whose answer depends on another question still open in this round belongs to a _later_ round, not this one.

Finding _facts_ is your job, never the user's. When a frontier question needs a fact from the environment (filesystem, tools, etc.), dispatch a sub-agent to find it; don't ask the user for anything you could look up yourself. Don't block on it: a running exploration is an unsettled prerequisite, so only the questions downstream of it wait for the sub-agent to report; ask the rest of the frontier now. The _decisions_ are the user's: put each to them and wait.

The session is done when the frontier is empty: every branch of the design tree visited, nothing left silently assumed. Do not act on it until the user confirms you have reached a shared understanding.
