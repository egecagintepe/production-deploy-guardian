# Contributing to Production Deploy Guardian

We welcome contributions from engineers, DevOps practitioners, and agent developers!

## Development Guidelines

1. **Zero External Dependencies**: The core CLI must remain strictly based on Python's standard library to guarantee portability across minimal agent sandboxes and container runners.
2. **Deterministic Behavior**: Classification rules and safety audits must be deterministic and reproducible.
3. **Automated Testing**: Any new rule, scanner pattern, or classification trigger must include comprehensive unit tests under `tests/`.
4. **Code Quality**: Ensure code is cleanly formatted and passes `unittest`:
   ```bash
   python -m unittest discover -s tests
   ```

## Pull Request Process

1. Fork the repository and create your feature branch from `main`.
2. Ensure all tests pass across platforms.
3. Update `CHANGELOG.md` under an `[Unreleased]` section.
4. Submit your pull request with a clear description of the motivation and behavior changes.
