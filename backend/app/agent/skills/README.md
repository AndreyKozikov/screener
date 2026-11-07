# Skills for the BondsScreener agent

Add each skill as a separate directory named with lowercase letters, numbers,
and hyphens. The directory name must match the `name` field in `SKILL.md`.

```text
skills/
└── bond-screening/
    ├── SKILL.md
    ├── references/   # Optional Markdown files linked from SKILL.md
    ├── scripts/      # Optional scripts; the agent does not execute these
    └── assets/       # Optional supporting files
```

`SKILL.md` must start with YAML frontmatter containing `name` and `description`,
followed by the skill instructions in Markdown. Discovery reads only the YAML
frontmatter. The selector receives names and descriptions; the full `SKILL.md`
body is read and added to the router prompt only after the LLM selects that skill.
Linked Markdown files under `references/` are also loaded only for a selected
skill. Scripts are not executed by the agent. With no valid skill folders, the
agent uses its base rules. If selection fails or returns no match, no skill
instructions are loaded.

Always applicable instructions belong in `../rules/`, not in a skill. Keep each
skill focused on one optional task capability.
