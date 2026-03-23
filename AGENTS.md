# AGENTS.md
Repo-wide guidance for coding agents working in this repository.

## Repo Layout
- `src/python/`: Python packages, service code, scripts, and tests. Most packages map to one ARCOR2 service or robot
  integration.
- `src/docker/`: Docker image definitions packaged through Pants `docker_image` targets.
- `3rdparty/`: Central Python dependency declarations and generated lockfiles for runtime and tool resolves.
- `build-support/`: Helper scripts used by CI and local setup.
- `compose-files/`: Demo and deployment compose stacks. `compose-files/fit-demo` is the easiest no-hardware smoke path.
- `pants-plugins/`: Local Pants macros and plugins.

## Working Rules
- Use Pants as the primary entry point for linting, type checking, tests, packaging, and BUILD-file maintenance.
- Keep dependency declarations centralized in `3rdparty/`; do not introduce ad-hoc per-package requirements files.
- Treat `3rdparty/constraints.txt` and `3rdparty/*_lockfile.txt` as generated artifacts. Edit the matching
  `*requirements.txt` inputs, then regenerate them with Pants.
- Keep changes scoped to the relevant package or service. Avoid broad refactors across unrelated `src/python/arcor2_*`
  packages unless the task explicitly requires it.
- Prefer ASCII-only edits unless the file already requires non-ASCII content.

## Dependencies and Packaging
- When runtime dependencies change, update `3rdparty/requirements.txt` and regenerate lockfiles with
  `pants generate-lockfiles`.
- When tool dependencies change, update the matching file in `3rdparty/` (`mypy-requirements.txt`,
  `pytest-requirements.txt`, `flake8-requirements.txt`, `setuptools-requirements.txt`) and regenerate lockfiles.
- Keep ROS Jazzy packages in `build-support/install_ur_dependencies.sh` pinned unless the goal is a deliberate UR stack
  upgrade. Those pins keep host-side tests and the `arcor2_ur` image on the same stack over time.
- Do not reintroduce exact Ubuntu package pins in Dockerfiles unless there is a clear reproducibility reason and the
  hadolint policy is updated with it.

## CI And Verification
- Start with focused Pants commands over the touched scope, then widen only if needed. Run one Pants command at a
  time.
- Common verification commands:
  - `pants update-build-files :: --check`
  - `pants lint`
  - `pants check`
  - `source /opt/ros/jazzy/setup.bash && pants test ::`
  - `pants package ::`
- For Docker changes, also run:
  - `pants lint src/docker::`
  - `pants --filter-target-type=docker_image --changed-since=origin/master --changed-dependents=transitive package`
- For Python distribution changes, keep the package-validation step green:
  - `pants --filter-target-type=python_distribution package ::`
  - install `dist/*.tar.gz` into a fresh virtualenv
  - `pip install "pipdeptree==2.30.0" && pipdeptree -w fail`
- If BUILD metadata may have drifted after file moves or new modules, run `pants update-build-files ::` before
  handoff.

## Docs
- Keep `README.md` high-level and user-facing. Put deeper developer workflow notes in the wiki or focused docs.
- Update docs when changing developer workflow, release flow, CI behavior, or dependency policy.
- By default, do not create git commits unless the user explicitly asks for one.
