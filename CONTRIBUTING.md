# Contributing to SecuNet

Thank you for your interest in contributing to SecuNet! Whether you're fixing a bug, proposing a new feature, improving documentation, or triaging issues — every contribution is valued and appreciated.

Please read these guidelines before getting started.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Ways to Contribute](#ways-to-contribute)
- [Reporting Bugs](#reporting-bugs)
- [Suggesting Features](#suggesting-features)
- [Development Setup](#development-setup)
- [Branch & Commit Conventions](#branch--commit-conventions)
- [Submitting a Pull Request](#submitting-a-pull-request)
- [Code Style & Standards](#code-style--standards)
- [Security Vulnerabilities](#security-vulnerabilities)
- [License](#license)

---

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you agree to uphold a welcoming and respectful environment for everyone.

---

## Ways to Contribute

- **Bug reports** — Found something broken? Open an issue.
- **Feature requests** — Have an idea? Share it with the community.
- **Code contributions** — Fix bugs, implement features, improve performance.
- **Documentation** — Improve the README, add inline comments, write guides.
- **Testing** — Write tests, reproduce reported bugs, validate fixes.
- **Triage** — Help label and prioritize open issues.

---

## Reporting Bugs

Before opening a new issue, please [search existing issues](https://github.com/sup3rus3r/secunet/issues) to avoid duplicates.

When filing a bug report, include:

- **A clear and descriptive title**
- **Steps to reproduce** the problem
- **Expected behavior** vs. **actual behavior**
- **Environment details**: OS, Docker version, Python version, Node.js version
- **Relevant logs or error messages** (redact any secrets)
- **Screenshots or recordings** if applicable

> **Do not include API keys, passwords, target IP ranges, or other sensitive information in issues.**

---

## Suggesting Features

Feature requests are welcome. To suggest a new feature:

1. [Search existing issues](https://github.com/sup3rus3r/secunet/issues) to see if it has already been proposed.
2. Open a new issue with the label `enhancement`.
3. Describe the problem your feature solves and your proposed solution.
4. Provide any relevant examples, mockups, or references.

For large or breaking changes, please open an issue to discuss before submitting a PR.

---

## Development Setup

### Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.12+ |
| Node.js | 18+ |
| Docker | 24+ |
| Docker Compose | v2+ |
| [uv](https://docs.astral.sh/uv/) | latest |

### 1. Fork and Clone

```bash
git clone https://github.com/your-username/secunet.git
cd secunet
```

### 2. Full stack (Docker)

```bash
cp .env.example .env   # fill in required variables
make up
```

### 3. Local development (no Docker)

```bash
# Start infrastructure
make dev-redis
make dev-postgres
make dev-mongo

# Start services
make dev-backend    # port 8000
make dev-cc         # port 8001
make dev-dashboard  # port 3000
```

---

## Branch & Commit Conventions

### Branch Naming

| Prefix | Purpose |
|--------|---------|
| `feature/` | New features or enhancements |
| `fix/` | Bug fixes |
| `docs/` | Documentation-only changes |
| `refactor/` | Code refactoring without behavior change |
| `test/` | Adding or updating tests |
| `chore/` | Maintenance, dependency updates, tooling |

### Commit Messages

Follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

```
<type>(<scope>): <short description>

[optional body]
```

**Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

Examples:
```
feat(recon): add masscan integration for fast host discovery
fix(hitl): resolve race condition in approval queue
docs(readme): update quick start instructions
```

---

## Submitting a Pull Request

1. **Ensure your branch is up to date** with `main`:
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Keep PRs focused** — one logical change per PR.

3. **Test your changes** locally before submitting.

4. **Open the PR against `main`** with:
   - A clear title following the commit convention
   - A description of what changed and why
   - References to related issues (`Closes #42`)
   - Screenshots for UI changes

### PR Checklist

- [ ] Code follows the project's style guidelines
- [ ] No secrets, credentials, API keys, or target IP ranges are included
- [ ] Backend changes include appropriate error handling
- [ ] Frontend changes tested in the browser
- [ ] Documentation updated where necessary
- [ ] Commit history is clean and follows conventions

---

## Code Style & Standards

### Python (Backend / Agents)

- **Type hints** on all function signatures
- **Pydantic models** for all request/response schemas
- **Async/await** consistent with FastAPI conventions
- No direct `anthropic` or `openai` imports in agents — all LLM calls go through `llm_client` / `base_agent._llm_complete()`
- No unused imports or dead code

### TypeScript (Dashboard)

- TypeScript — avoid `any` types
- Functional React components with hooks
- Follow existing Zustand store patterns
- Tailwind CSS utility classes — avoid inline styles

### General

- Write self-documenting code; add comments only where logic is non-obvious
- Do not introduce new dependencies without prior discussion

---

## Security Vulnerabilities

**Do not report security vulnerabilities through public GitHub issues.**

See [SECURITY.md](SECURITY.md) for responsible disclosure instructions.

---

## License

By contributing to SecuNet, you agree that your contributions will be licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**.

See the [LICENSE](LICENSE) file for full terms.

---

*Thank you for helping make SecuNet better.*
