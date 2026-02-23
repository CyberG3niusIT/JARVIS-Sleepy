# Contributing to JARVIS

Thank you for your interest in contributing to JARVIS! This guide will help you get started.

## How to Contribute

### Reporting Bugs

Found a bug? Please [open an issue](https://github.com/InterGenJLU/jarvis/issues/new?template=bug_report.md) with:

- A clear description of the problem
- Steps to reproduce
- Expected vs. actual behavior
- Your environment details (OS, Python version, GPU, ROCm version)
- Relevant log output (`journalctl --user -u jarvis -n 50`)

### Suggesting Features

Have an idea? [Open a feature request](https://github.com/InterGenJLU/jarvis/issues/new?template=feature_request.md) describing:

- The problem or use case
- Your proposed solution
- Any alternatives you've considered

### Submitting Code

1. **Fork** the repository
2. **Create a branch** from `main`: `git checkout -b feature/your-feature`
3. **Make changes** incrementally, testing after each change
4. **Commit** with clear, imperative-style messages (e.g., "Add weather forecast caching")
5. **Push** your branch and open a **Pull Request**

## Development Setup

See [docs/SETUP_GUIDE.md](docs/SETUP_GUIDE.md) for full installation instructions.

Quick summary:
- **Python 3.12** on Ubuntu 24.04 LTS
- **AMD ROCm** for GPU acceleration (RX 7900 XT reference hardware)
- **llama.cpp** with ROCm backend for local LLM inference

```bash
git clone https://github.com/InterGenJLU/jarvis.git
cd jarvis
pip install -r requirements.txt
cp .env.example .env  # Add your API keys
```

## Creating Skills

JARVIS uses a modular skill system with semantic intent matching. See [docs/SKILL_DEVELOPMENT.md](docs/SKILL_DEVELOPMENT.md) for the complete guide, including:

- Skill directory structure
- Registering semantic intents
- Testing with voice commands
- Example skill template

## Code Style

- **Python** — Follow existing patterns in the codebase
- **Imports** — Standard library first, then third-party, then local
- **No linter enforced** yet, but keep code clean and readable
- **Avoid** adding `torch` imports to `core/stt.py` (historical GPU isolation convention)

## Commit Messages

Follow the existing style:

- Use imperative mood: "Add feature" not "Added feature"
- Keep the first line under 72 characters
- Reference issues where relevant: "Fix wake word sensitivity (#42)"

## Testing

- Run edge case tests: `python scripts/test_edge_cases.py`
- Test voice commands manually after changes to core pipeline
- Verify GPU acceleration is still active after changes

## Documentation

- Update relevant docs when changing behavior
- Skill changes should update the skill's own documentation
- Keep README.md in sync with new features

## Questions?

Open a [discussion](https://github.com/InterGenJLU/jarvis/issues) or check the existing [documentation](docs/).
