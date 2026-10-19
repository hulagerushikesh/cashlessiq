# Domain boundary

The authoritative pure-Python core remains in `src/cashlessiq/rules` until a
dedicated migration preserves all fixtures in `tests/fixtures/migration/v1.json`.
Do not duplicate the rules here or add framework dependencies to the core.
