# Prompt 01: Interview me about my data

**When:** Lab 1, after your paper sketch. **Writes code?** No.

## Why this prompt is shaped like this

Remember the four levers from Session 2: **specificity, constraints, context, iteration**. This prompt leans on **context** (the agent reads your AGENTS.md and your description of the app) and **constraints** ("write NO code", "one question at a time", "do not decide anything for me"). It also turns **iteration** into a conversation: the agent asks, you answer, and the design improves one question at a time. You are the expert on your business and the agent is not, so it asks and you decide. If it jumps ahead and writes SQL, that is context drift: reply "Stop. No code yet. Back to questions."

## The prompt

Copy everything in the box. Replace the [PLACEHOLDERS] first.

```text
You are helping me design the data model for my app. I am not a professional developer.
Read AGENTS.md first.

My app: [ONE OR TWO SENTENCES: WHAT IT DOES AND WHO USES IT]
My paper sketch has these things in it: [LIST THE BOXES ON YOUR SKETCH, e.g. member, equipment, loan]

Interview me about my data. Rules:
- Ask ONE question at a time and wait for my answer.
- Use plain English, no jargon. If you must use a database word, explain it in brackets.
- Ask about: what each thing is, which details are required, what must never be duplicated,
  which values are only allowed from a fixed list or within limits, how the things connect,
  and what should happen to connected records when something is deleted.
- Do NOT write any code, SQL or schema.
- Do NOT decide anything for me. If I am unsure, give me the options and what each means.
- Stop after about 10 questions.

When the interview is finished, draft docs/data-model.md using the template already in that
file. Fill in the tables, the relationships, the delete rule section (with MY reason in my
words) and a Mermaid erDiagram. Mark anything you guessed with "(GUESS: please check)".
Then list any decision you made that I did not specify.
```

## After it answers

Open `docs/data-model.md` and correct it yourself. Delete every "(GUESS: please check)" by either fixing it or confirming it. **The delete rule must be your decision.** Then commit:

```text
git add docs/data-model.md
git commit -m "Add data model (written before generating the schema)"
```
