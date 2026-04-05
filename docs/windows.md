# Windows Setup

Windows-specific installation and usage notes.

---

## Installation on Windows

### Via winget (Recommended)

Claude Code supports Windows Package Manager:

```powershell
winget install Anthropic.ClaudeCode
```

Then install the skill:

```
/plugin marketplace add OthmanAdi/planning-with-files
/plugin install planning-with-files@planning-with-files
```

### Manual Installation

```powershell
# Create plugins directory
mkdir -p $env:USERPROFILE\.claude\plugins

# Clone the repository
git clone https://github.com/OthmanAdi/planning-with-files.git $env:USERPROFILE\.claude\plugins\planning-with-files
```

### Skills Only

```powershell
git clone https://github.com/OthmanAdi/planning-with-files.git
Copy-Item -Recurse planning-with-files\skills\* $env:USERPROFILE\.claude\skills\
```

---

## Path Differences

| Unix/macOS | Windows |
|------------|---------|
| `~/.claude/skills/` | `%USERPROFILE%\.claude\skills\` |
| `~/.claude/plugins/` | `%USERPROFILE%\.claude\plugins\` |
| `.claude/plugins/` | `.claude\plugins\` |

---

## Shell Script Compatibility

The helper scripts (`init-session.sh`, `check-complete.sh`) are bash scripts.

### Option 1: Use Git Bash

If you have Git for Windows installed, run scripts in Git Bash:

```bash
./scripts/init-session.sh
```

### Option 2: Use WSL

```bash
wsl ./scripts/init-session.sh
```

### Option 3: Manual alternative

Instead of running scripts, manually create the files:

```powershell
# Copy templates to current directory
Copy-Item templates\task_plan.md .
Copy-Item templates\findings.md .
Copy-Item templates\progress.md .
```

---

## Hook Commands

The hooks use Unix-style commands. On Windows with Claude Code:

- Hooks are dispatched through `sh -lc` so they behave consistently even when Claude Code launches them from PowerShell
- Ensure Git Bash (or another `sh` implementation) is installed and available on your `PATH`
- The Stop hook still prefers `check-complete.ps1` on Windows after the `sh` wrapper resolves the script path

---

## Common Windows Issues

### Path separators

If you see path errors, ensure you're using the correct separator:

```powershell
# Windows
$env:USERPROFILE\.claude\skills\

# Not Unix-style
~/.claude/skills/
```

### Line endings

If templates appear corrupted, check line endings:

```powershell
# Convert to Windows line endings if needed
(Get-Content template.md) | Set-Content -Encoding UTF8 template.md
```

### Permission errors

Run PowerShell as Administrator if you get permission errors:

```powershell
# Right-click PowerShell → Run as Administrator
```

---

## Terminal Recommendations

For best experience on Windows:

1. **Windows Terminal** - Modern terminal with good Unicode support
2. **Git Bash** - Unix-like environment on Windows
3. **WSL** - Full Linux environment

---

## Need Help?

Open an issue at [github.com/OthmanAdi/planning-with-files/issues](https://github.com/OthmanAdi/planning-with-files/issues).
