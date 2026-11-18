# Project instructions

- All user interface text and visible content must be in standard Catalan.
- Code, identifiers, comments, and technical documentation must be in English.
- Keep the Django application modular, simple, and maintainable.
- Prioritize family data and do not modify existing Home Server services.
- Work incrementally, with tests and without overengineering.
- Do not introduce dependencies or functionality that have not been requested.
- The consolidated V1 baseline in [docs/specs](docs/specs/README.md) and the replacement [UX design](docs/ux/README.md) supersede legacy specifications and mockups.
- Compliance with `ARCHITECTURE.md` is mandatory for all future implementations. Follow its architectural principles, dependency boundaries, and testing strategy pragmatically.
- Use the complete V1 specification and acceptance criteria throughout M0–M8. Apply rolling planning to implementation details within the approved boundaries.
- Deliver vertical slices using automated quality gates. Record owner QA separately and require consolidated manual owner QA before release.
- Past weekly menus are strictly read-only; current and future weeks are editable. Recipe changes update affected current and future shopping lists while preserving historical data.
- Do not introduce application-level authentication. Limit access to the trusted household LAN and verify actual network isolation before release.
