"""Deterministic symptom -> signal -> resolution diagnostics engine.

No LLM, no network call, no API key. Every finding here is either read
directly off disk (plugin headers, modlist.txt, file-conflict winners) or
derived from the resolution_policy this project has already committed to.
That is a deliberate scope decision, not a shortcut: this engine can
rename and hide files inside your MO2 install when you pass --apply, so
every action it takes has to be traceable to a rule you can read in
rules.py, not a black-box inference.

Deliberately NOT reimplemented here: Buffout 4 crash-log parsing (CLASSIC
-- github.com/GuidanceOfGrace/CLASSIC-Fallout4 -- already does this well;
see rules.py's CLASSIC pointer finding) and FormID/record-level plugin
conflict resolution (xEdit's job, not a loose-file manager's). Both were
checked against prior art before building anything here, not assumed to
need a custom solution.
"""
