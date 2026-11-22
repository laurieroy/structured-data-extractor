# Agent Setup (M0): Protecting Secrets

Do this first, before any other project file is created. Ask the user to confirm, then
work through the items below. Status reflects what is already in the repo.

## 1. `.gitignore` — DONE

Already covers `__pycache__/`, `.venv/`, `.env`, `.env.*` (with `!.env.example`),
`.pytest_cache/`, `dlq/`, `.streamlit/secrets.toml`, `.devin/config.local.json`.

## 2. `.devin/config.json` — DONE

Created with deny rules blocking read/write/shell access to real env files and
secrets. Deny rules
always win and can't exempt `.env.example`, so variants are listed by name:

```json
{
  "permissions": {
    "deny": [
      "Read(.env)",
      "Read(.env.local)",
      "Read(.env.development)",
      "Read(.env.production)",
      "Read(.env.test)",
      "Read(.env.*.local)",
      "Read(.streamlit/secrets.toml)",
      "Write(.env)",
      "Write(.env.local)",
      "Write(.env.development)",
      "Write(.env.production)",
      "Write(.env.test)",
      "Write(.env.*.local)",
      "Write(.streamlit/secrets.toml)",
      "Exec(cat .env)",
      "Exec(cat .env.local)",
      "Exec(cat .streamlit/secrets.toml)"
    ]
  }
}
```

Note: `Exec` rules are command-prefix matched and only cover the obvious `cat`
invocations — the `Read`/`Write` denies are the real guard. Devin's Smart mode also
never auto-approves reads/writes of dotenv files, key material, or agent config.

## 3. `.env.example` — DONE (placeholders verified)

Only `.env.example` may be created or edited, with placeholder values only
(`OPENAI_API_KEY=your-key-here`, `ANTHROPIC_API_KEY` per the provider decision,
`EXTRACTOR_MODEL`).

## 4. User verification — TODO

Tell the user to run `git status` and confirm `.env` is not tracked before the first
commit.
