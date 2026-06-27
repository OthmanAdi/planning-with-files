# OpenClaw Setup

How to use planning-with-files with [OpenClaw](https://openclaw.ai).

---

## What This Integration Adds

- Workspace skill: `skills/planning-with-files/` in your project root
- Full templates, scripts, and reference documentation
- Cross-platform support (macOS, Linux, Windows)

OpenClaw supports three skill locations (in precedence order):
1. **Workspace skills** (highest priority): `<workspace>/skills/`
2. **Managed/local skills**: `~/.openclaw/skills/`
3. **Bundled skills** (lowest priority): shipped with install

---

## Installation (via ClawHub — recommended)

Install directly from the ClawHub marketplace:

```bash
claw install othmanadi/planning-with-files
```

Or download the zip from [clawhub.ai/othmanadi/planning-with-files](https://clawhub.ai/othmanadi/planning-with-files) and extract to your workspace `skills/` folder.

---

## Installation (Workspace, manual)

Copy from the GitHub repo to your project:

```bash
# Clone the repo
git clone https://github.com/OthmanAdi/planning-with-files.git

# Copy the skill files to your workspace
mkdir -p skills/planning-with-files
cp -r planning-with-files/skills/planning-with-files/* skills/planning-with-files/

# Clean up
rm -rf planning-with-files
```

---

## Installation (Global)

Install to your local OpenClaw skills directory:

```bash
# Clone the repo
git clone https://github.com/OthmanAdi/planning-with-files.git

# Copy to global OpenClaw skills
mkdir -p ~/.openclaw/skills/planning-with-files
cp -r planning-with-files/skills/planning-with-files/* ~/.openclaw/skills/planning-with-files/

# Clean up
rm -rf planning-with-files
```

---

## Verify Installation

```bash
# Check OpenClaw status and loaded skills
openclaw status
```

---

## Usage

1. Start an OpenClaw session in your project directory
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

Configure the skill in `~/.openclaw/openclaw.json`:

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

- OpenClaw snapshots eligible skills when a session starts
- Workspace skills take precedence over bundled skills
- The skill works on all platforms: macOS, Linux, and Windows
- Planning files are tool-agnostic and work across Claude Code, Cursor, and other IDEs
