# Clawd CLI Setup

How to use planning-with-files with [Clawd CLI](https://clawd.bot).

---

## What This Integration Adds

- Workspace skill: `.clawd/skills/planning-with-files/`
- Full templates, scripts, and reference documentation
- Cross-platform support (macOS, Linux, Windows)

Clawd CLI supports three skill locations (in precedence order):
1. **Workspace skills** (highest priority): `<workspace>/skills/`
2. **Managed/local skills**: `~/.clawdbot/skills/`
3. **Bundled skills** (lowest priority): shipped with install

---

## Installation (Workspace, recommended)

Copy the skill to your project:

```bash
# Clone the repo
git clone https://github.com/OthmanAdi/planning-with-files.git

# Copy the Clawd skill to your workspace
cp -r planning-with-files/.clawd/skills/planning-with-files skills/

# Clean up
rm -rf planning-with-files
```

---

## Installation (Global)

Install to your local Clawd skills directory:

```bash
# Clone the repo
git clone https://github.com/OthmanAdi/planning-with-files.git

# Copy to global Clawd skills
mkdir -p ~/.clawdbot/skills
cp -r planning-with-files/.clawd/skills/planning-with-files ~/.clawdbot/skills/

# Clean up
rm -rf planning-with-files
```

---

## Installation (ClawdHub)

If available on ClawdHub:

```bash
clawdhub install planning-with-files
```

---

## Verify Installation

```bash
# List all skills
clawdbot skills list

# Check if planning-with-files is loaded
clawdbot skills info planning-with-files
```

---

## Usage

1. Start a Clawd session in your project directory
2. For complex tasks, the skill will guide you to create:
   - `task_plan.md` — Phase tracking and decisions
   - `findings.md` — Research and discoveries
   - `progress.md` — Session log and test results
3. Follow the workflow: plan first, update after each phase

---

## Helper Scripts

From your project root:

```bash
# Initialize all planning files
bash skills/planning-with-files/scripts/init-session.sh

# Or on Windows PowerShell
powershell -ExecutionPolicy Bypass -File skills/planning-with-files/scripts/init-session.ps1

# Verify all phases are complete
bash skills/planning-with-files/scripts/check-complete.sh
```

---

## Configuration (Optional)

Configure the skill in `~/.clawdbot/clawdbot.json`:

```json5
{
  skills: {
    entries: {
      "planning-with-files": {
        enabled: true
      }
    }
  }
}
```

---

## Notes

- Clawd CLI snapshots eligible skills when a session starts
- Workspace skills take precedence over bundled skills
- The skill works on all platforms: macOS, Linux, and Windows
- Planning files are tool-agnostic and work across Claude Code, Cursor, and other IDEs
