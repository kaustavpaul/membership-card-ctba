# Recoverable checkpoint

**Tag:** `checkpoint-before-features`  
**Commit:** `e1f7c15` — Fix NameError from PIL type annotations

This tag marks the stable state before planning new feature additions.

## To restore this state later

```bash
# Discard all local changes and return to this exact state
git checkout checkpoint-before-features

# Or create a new branch from this point (keeps current branch intact)
git branch recovery-from-checkpoint checkpoint-before-features
git checkout recovery-from-checkpoint
```

## To push the tag to remote (optional)

```bash
git push origin checkpoint-before-features
```

You can delete this file after you're done with the feature work if you prefer.
