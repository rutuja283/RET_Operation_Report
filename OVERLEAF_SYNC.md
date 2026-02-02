# Overleaf GitHub Sync Setup

## Step-by-Step Instructions

### 1. Commit and Push Changes to GitHub

Run these commands in your terminal:

```bash
cd /Users/rutuja/Desktop/RET_Operation_Report

# Add automation files (scripts, docs, config)
git add scripts/ .gitignore requirements.txt README.md QUICKSTART.md SETUP_GUIDE.md AUTOMATION_SUMMARY.md main.tex

# Commit
git commit -m "Add automation pipeline for report generation"

# Push to GitHub
git push
```

### 2. Connect Overleaf to GitHub

1. **In Overleaf:**
   - Open your La Sal Operations Report project
   - Click **Menu** (top left)
   - Select **GitHub**
   - Click **Link GitHub Account** (if not already linked)
   - Authorize Overleaf to access your GitHub

2. **Link the Repository:**
   - Click **Link a GitHub Repo**
   - Select your repository: `RET_Operation_Report` (or whatever it's named)
   - Choose the branch (usually `main` or `master`)
   - Click **Link**

### 3. Sync Workflow

**From Local → Overleaf:**
- After generating plots locally, commit and push:
  ```bash
  git add plots/*.png main.tex
  git commit -m "Update report for Dec 2025"
  git push
  ```
- In Overleaf, click **Pull from GitHub** to sync

**From Overleaf → Local:**
- If you make changes in Overleaf, click **Push to GitHub**
- Then locally: `git pull`

### 4. Automated Workflow

**Monthly Report Generation:**

1. **Local (your computer):**
   ```bash
   cd scripts
   python complete_pipeline.py 12 2025
   ```

2. **Commit and push:**
   ```bash
   cd ..
   git add plots/*.png main.tex
   git commit -m "Generate report for Dec 2025"
   git push
   ```

3. **In Overleaf:**
   - Click **Pull from GitHub**
   - Compile the PDF
   - Review and download

## Important Notes

### Files to Keep in Sync

✅ **Push these:**
- `main.tex` (updated with plot references)
- `plots/*.png` (generated plots)
- `scripts/` (automation scripts)
- Documentation files

❌ **Don't push (already in .gitignore):**
- `data/csv/*.csv` (data files - too large/sensitive)
- `data/raw/*.pdf` (original PDFs - too large)
- `*.aux`, `*.log` (LaTeX temporary files)

### Overleaf Compilation

- Overleaf will compile `main.tex` automatically
- Make sure all plot files exist in `plots/` directory
- If compilation fails, check that plot filenames match in `main.tex`

### Plot File Naming

Plots are named with format: `{YYYY}{MM}_PlotName_Report.png`
- Example: `202512_OperatingSchedule_Report.png`
- The `update_latex.py` script automatically updates references

## Troubleshooting

### "Plot file not found" in Overleaf

- Check that plot files were pushed to GitHub
- Verify filenames match exactly (case-sensitive)
- Ensure plots are in `plots/` directory in repository

### Sync Conflicts

If you have conflicts:
1. In Overleaf: **Pull from GitHub** first
2. Resolve any conflicts
3. Then make your changes
4. Push back to GitHub

### Large Files

If plots are too large for GitHub:
- Consider using Git LFS: `git lfs track "plots/*.png"`
- Or compress plots before committing
- Or store plots elsewhere and reference URLs

## Best Practices

1. **Always pull before pushing** to avoid conflicts
2. **Generate plots locally** (faster, no Overleaf compute limits)
3. **Commit plot updates separately** from code changes
4. **Use descriptive commit messages** with month/year

## Quick Reference

```bash
# Generate report
cd scripts
python complete_pipeline.py 12 2025

# Commit and push
cd ..
git add plots/*.png main.tex
git commit -m "Update report for Dec 2025"
git push

# Then in Overleaf: Pull from GitHub → Compile
```
