# Prompt 05: What did you decide that I did not?

**When:** end of Lab 2, before you commit and push. Also useful any time an agent has been working for a while. **Writes code?** No.

## Why this prompt is shaped like this

Every agent fills the gaps in your instructions with its own choices, and usually does not mention them. In Session 2 we met **hallucination** and **context drift**; this prompt is the habit that catches both. It is pure **specificity** about the output (a table you can paste straight into your AI-usage log) plus one **constraint** ("do not change any files"). What comes back is direct evidence for the **Discernment** part of your AI Fluency declaration: what you accepted, modified or rejected, and why.

## The prompt

```text
Do not change any files. Look back over everything you have done in this conversation and
in this project today.

List every decision you made that I did not explicitly specify. Include names you chose,
data types, limits, default values, delete behaviour (ON DELETE), error handling, libraries,
file locations, and anything you removed or rewrote.

Give me a table with these columns:
| Decision | What you chose | What else you could have chosen | Why you chose it | Risk if it is wrong |

Then tell me which ONE of these decisions you think I should check first, and why.
```

## After it answers

1. Read the table. For each row, decide: **keep**, **change** or **reject**.
2. Paste the table into `docs/ai-usage-log.md` under today's entry, and add your keep/change/reject decision and reason to each row.
3. Anything you changed: note it in "What I changed after testing" in `docs/data-model.md`, and add it to "Decisions I have made" in `AGENTS.md`.
4. Commit: `git add docs AGENTS.md` then `git commit -m "Log AI decisions from data layer work"`.
