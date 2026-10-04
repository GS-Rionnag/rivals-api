# Incremental releases

The chat chooses the smallest correct semantic version bump when a release is
requested. Prefer small, focused changes and retain compatibility so routine
work can ship as patch or minor releases. State the selected version and a short
reason before publishing; there is no separate version-selection approval step.

Versions have three integer components, `major.minor.patch`, rather than decimal
arithmetic. The user's release sizes map to:

| Requested size | Version component | Use for | Example from 4.0.0 |
| --- | --- | --- | --- |
| `0.01` | Patch | Compatible bug fixes, accuracy corrections that honor the documented contract, and internal improvements | `4.0.1` |
| `0.1` | Minor | New optional arguments, methods, or features that preserve existing behavior | `4.1.0` |
| `1` | Major | Necessary incompatible changes to public methods, accepted arguments, defaults, response shapes, or documented meanings | `5.0.0` |

Choose based on the public contract, not the number of files or lines changed.
For mixed changes, use the highest required component. Reset the components to
its right: `4.2.7` becomes `4.2.8`, `4.3.0`, or `5.0.0`.

Before selecting a major bump, look for a compatible implementation: add an
optional argument or separately named method, retain an alias, or deprecate the
old behavior with a documented migration. Split independent work into focused
releases where practical. If the requested behavior still requires a breaking
change, explain the concrete incompatibility and obtain explicit user
authorization before implementing the breaking change or publishing a major
release. A general "push and release" request does not authorize a major bump.
Do not label a breaking release as a patch or minor just to keep the number small.

## Publishing

1. Confirm that the user requested a release. A request to push commits alone
   does not imply publishing a GitHub release or a PyPI package. Documentation
   and repository instruction changes normally require no package version bump.
2. Check the current package version and published releases/tags to avoid
   collisions. Never downgrade the version or rewrite an existing published tag.
3. Choose the bump using the rules above. Update `pyproject.toml` and
   `src/rivals_api/__init__.py` together, plus version references in project
   context. Add user-facing changes and any migration steps to
   `docs/CHANGELOG.md`.
4. Run checks appropriate to the changes and build the package. For a code
   release, run the test suite, Ruff, and `python -m build`; inspect the resulting
   package version and contents.
5. Commit and push the release changes. Publish the GitHub release with a
   `v<version>` tag pointing to the intended commit. Attach the matching wheel
   and source archive. Publishing a GitHub release triggers the PyPI workflow.
6. Verify the publication workflow and the version on PyPI. Report the actual
   outcome and link the release; do not call it published until verified.

The existing `4.0.0` release remains published. These rules apply to future work.
