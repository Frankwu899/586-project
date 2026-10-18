# Video Anatomy: workspace redesign review

Status: **Design proposal for discussion. Not an application update.**

This review responds to the owner's hands-on macOS test: the product behaves like
a rigid four-step form, recording chrome pollutes evidence, processing feedback
is easy to miss, and the analysis layout does not support working with time.

Read in this order:

1. [Product and interaction proposal](DESIGN_SPEC.md): user goals, entry paths,
   workspace behavior, local files, desktop delivery and decisions still open.
2. [Clickable concept](prototype.html): a self-contained HTML file intended to
   open directly in a browser. Its analysis and activity states are simulated.
   It does not change the installed application or tasks, and needs no API key
   or paid service. Local HTTP testing passed; see the direct-file test limit below.
3. [Design skill provenance](SKILL_INSTALLATION.md): the explicitly requested
   design skill, installed version, relevant search results and rejected advice.
4. [Verification and limits](CHECKS.md): tested interactions and capabilities
   that are not implemented or not yet verified on macOS.

To review on a Mac, extract the ZIP into a new folder and open `prototype.html`
with Safari or Chrome. Do not replace the existing application folder. Local
file opening could not be tested in the managed Cloud browser because its policy
blocks `file://`; the prototype has no external scripts, fonts or fetch calls.
If a browser restricts local-file storage, the interface still works but draft
recovery may be unavailable. An optional local HTTP fallback is:

```bash
python3 -m http.server 8768 --bind 127.0.0.1
```

Run that command from the extracted review folder, then open
`http://127.0.0.1:8768/prototype.html`. This is a design review, not the application
launcher or a replacement installation. Stop the server with Control-C.

The concept is a review tool. An attractive layout does not establish recognition
accuracy, a working background queue, cropping, research retrieval or a macOS
installer. The source application remains unchanged in this round.

## Walk through three situations

- Study a saved reference without creating a brand brief. Select timeline evidence
  and inspect it beside the video. Preview content-area and local feedback states.
- Open Ideas while reference work is unfinished. Draft an idea and choose whether
  reference material should inform it. This is a proposed workflow expansion.
- Open Production to inspect a plan. Approve an idea before asking for a generated
  production draft. Existing work should remain accessible throughout.

Evaluate whether the next useful action is clear, whether feedback stays near the
action, and whether moving among workspaces preserves the current task. Review
the interaction before judging the glass treatment.

All new installer, launcher, package instructions and handoff materials must be
in English. Chinese conversation, source evidence and explicitly selected Chinese
generation output remain supported. Existing Chinese launcher messages need to be
replaced in the next implementation release; this design round does not silently
change the owner's installed copy.
