# Proposed GitHub publication commands

**Documentation only** for operators. Copyright is already set to Weblytic Labs.

These commands assume:

- Staging tree path stored in `STAGING` (your local path to this folder)
- Remote: `https://github.com/wblcollaborators/gaming-pc-api-docs.git`
- `gh` authenticated as the publisher

## 1. Confirm Weblytic Labs copyright notices

```bash
cd "$STAGING"
grep -n "Copyright (c) 2026 Weblytic Labs" LICENSE-NOTICE.md LICENSE-EXAMPLES-MIT.md README.md
```

## 2. Initialize Git (only after approval)

```bash
cd "$STAGING"
git init -b main
git add .
git status
git commit -m "$(cat <<'EOF'
Publish Universal Gaming PC API documentation and MIT integration examples

EOF
)"
```

## 3. Attach remote and push

```bash
git remote add origin https://github.com/wblcollaborators/gaming-pc-api-docs.git
git push -u origin main
```

## Do not

- Force-push to a shared `main` without approval
- Add `controller/` or `agent/` trees
- Commit `.env`, `*.pem`, `*.key`, or binaries
- Point `origin` at the private development repository
