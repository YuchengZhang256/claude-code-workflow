# Example: one-shot anchor alignment paper, cor:explicit-rate

Artifact produced by a Phase-2.3 chain-walk run inside a proof-audit-longform pipeline on `one_shot_anchor_alignment_paper_v2.tex`. Showcases the skill's target output shape: walked vs stated diff, two sev-5 chain-breaks on `cor:explicit-rate`, LaTeX patch options.

The chain-walk here found what 6 prior proof-audit rounds missed: `\lambda_{\min}^{-2}` missing on alignment branch, `K` missing on $\delta_W$ branch. This file is the primary motivating example for the skill.

Caveat: this example was run before the skill was formalized — its extraction went through ad-hoc GPT prompts rather than the skill's double-blind canary-gated pipeline, so real skill runs should produce comparable findings with stronger confidence floors.
