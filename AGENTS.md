# Repository instructions

@C:\Users\giris\.codex\RTK.md

## Keep changes incremental

Implement the requested change in small, focused steps. Preserve existing public
methods, arguments, defaults, and response shapes where practical. Use compatible
additions, aliases, and deprecation paths instead of bundling breaking changes
into a large release. Do not add unrelated features to justify a version bump.

## Choose the release size automatically

When the user requests a release, follow [docs/RELEASING.md](docs/RELEASING.md).
The chat chooses the smallest appropriate bump from the actual changes and
briefly states its choice and reason. Do not ask the user to choose the number.

- Patch (the user's "0.01"): compatible fixes; `4.0.0` becomes `4.0.1`.
- Minor (the user's "0.1"): compatible new features; `4.0.0` becomes `4.1.0`.
- Major (the user's "1"): necessary public API incompatibility; `4.0.0` becomes
  `5.0.0`. Requires explicit user authorization for a major/breaking release.

Preserve compatibility so ordinary requests stay patch or minor. A general
"push and release" request does not authorize a major bump. If compatibility
cannot be preserved, explain the concrete conflict and obtain explicit
authorization before implementing the breaking change or publishing a major.
Do not label an incompatible release as patch/minor to avoid this requirement.

A push alone does not require a release or version bump. Documentation-only
changes normally need neither. Do not rewrite published versions or release tags.
