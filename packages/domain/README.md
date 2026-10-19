# Domain boundary

The authoritative pure-Python core remains in `src/cashlessiq/rules` until a
dedicated migration preserves all fixtures in `tests/fixtures/migration/v1.json`.
Do not duplicate the rules here or add framework dependencies to the core.

## P2 source-validation distribution

`cashlessiq-domain` exposes the existing decision schema and three source
observation modules under the distinct `cashlessiq_domain` import namespace.
Its only runtime dependency is `jsonschema`. The API uses an explicit uv local
path dependency, not `sys.path` changes or the legacy application distribution
(which depends on Snowpark and Streamlit).

This is a temporary wheel-packaging bridge, not a physical domain migration.
Hatch includes an exact allowlist of four canonical files from `src/cashlessiq`;
there is no second editable implementation or import of the legacy package.
Relative imports allow the same source files to work in either namespace.
Do not exchange class instances between the two import namespaces. The API must
use `cashlessiq_domain` consistently. Rules, procedures and app code are excluded.

Build a wheel from the complete repository checkout, not a standalone source
distribution. `make product-domain-check` verifies wheel/source byte identity,
installs the wheel in a temporary isolated environment, and tests imports and
validation without the legacy package, Snowflake, Streamlit or FastAPI installed.
CI runs this check without Snowflake authentication or Docker. The API Dockerfile
copies only the canonical allowlisted files needed for the bridge and preserves
the relative local dependency layout.

The bridge follows [Hatch force-include](https://hatch.pypa.io/latest/config/build/)
and [uv path dependencies](https://docs.astral.sh/uv/concepts/projects/dependencies/#path).
Explicit uv cache keys include canonical source files outside this directory;
editing a validator must invalidate the installed dependency, not leave stale code.
