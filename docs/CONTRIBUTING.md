# Contributing to Machine Capacity Planner

Thank you for helping improve this project!

## Development Setup

```bash
# Clone
git clone https://github.com/YOUR_ORG/machine_capacity_planner
cd machine_capacity_planner

# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
pytest machine_capacity_planner/tests/ -v

# Run linter
flake8 machine_capacity_planner/

# Check formatting
black --check machine_capacity_planner/

# Auto-format
black machine_capacity_planner/
```

## Branch Strategy

| Branch | Purpose |
|--------|---------|
| `main` | Production releases only |
| `develop` | Integration branch — PR target |
| `feature/*` | New features |
| `fix/*` | Bug fixes |
| `hotfix/*` | Urgent production patches |

## Pull Request Process

1. Fork the repository
2. Create a `feature/your-feature` branch from `develop`
3. Write code + tests
4. Run `flake8` and `black --check` — both must pass
5. Open a PR targeting `develop`
6. PR description must reference an issue (e.g. `Fixes #42`)

## Code Style

- Follow PEP 8 with max line length 120
- Use `mcp_logger` for all logging (never `print()`)
- All public functions must have docstrings
- Use type hints for function signatures

## Test Coverage

- New features must include unit tests in `tests/test_machine_selector.py`
- Coverage must remain above 70%

## Commit Message Convention

```
feat: add weekly utilisation report
fix: handle zero horizon_hrs in score calculation
docs: update INSTALLATION.md with troubleshooting table
chore: bump version to 1.1.0
```
