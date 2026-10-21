---
name: grill-me
description: A relentless interview to sharpen a plan or design.
disable-model-invocation: true
---

Read and apply `../grilling/SKILL.md` from this project-local installation.
If the runtime has a Skill invocation tool, it may be used to invoke `grilling`;
otherwise read that file directly. Do not claim a missing tool was called.

## Owner-required interactive interview

Every interview question MUST be sent through the native interactive question
UI. In this Codex environment use `functions.request_user_input_async` in Default
mode; use `functions.request_user_input` only when the active mode permits it.
Do not render questions, option lists, or approval requests as plain chat text.
Do not repeat the question in commentary or the final answer after sending it.
Apply the matching transport rules in `../grilling/SKILL.md`.

Continue the existing conversation and confirmed decisions; the owner explicitly
requested this skill here. Installation and this customization are already
authorized. Using this interview skill does not authorize implementing the
product being discussed.
