# Contributing to video-mcp

**Repo:** https://github.com/MHughesDev/video-mcp  
**Default branch:** `master`

---

## Git Setup

Make sure your local repo is pointed at the right remote before doing anything:

```bash
# Verify remote
git remote -v
# Should show:
# origin  https://github.com/MHughesDev/video-mcp.git (fetch)
# origin  https://github.com/MHughesDev/video-mcp.git (push)

# If wrong, fix it:
git remote set-url origin https://github.com/MHughesDev/video-mcp.git
```

---

## Standard Git Workflow

### Start a new feature
```bash
git checkout master
git pull origin master
git checkout -b feat/your-feature-name
```

### Commit
```bash
git add <specific-files>
git commit -m "feat: short description of change"
```

### Push branch and open PR
```bash
git push -u origin feat/your-feature-name
# Then open a PR at: https://github.com/MHughesDev/video-mcp/compare
```

### Merge to master (after PR approval)
```bash
git checkout master
git pull origin master
```

---

## Commit Message Format

```
<type>: <short description>

Types: feat | fix | refactor | docs | chore | test
```

Examples:
```
feat: add trim tool to MCP server
fix: handle missing timecode in inspection tool
docs: update tool reference in docs/tools.md
```

---

## Pushing Directly to Master

Only for small, safe changes:

```bash
git checkout master
git pull origin master
# make changes
git add <files>
git commit -m "chore: description"
git push origin master
```

> Always confirm `git remote -v` shows `MHughesDev/video-mcp` before pushing.
