# Testing

## Running Tests

Run the default regression suite from the repository root:

```bash
python -m pytest
```

## Test Mode

Automated/default tests use:

```bash
INVENTORY_TEST_MODE=1
```

In this mode the application can be imported without live Supabase credentials. Tests must not connect to live Supabase and must not mutate `PILOT_PRODUCTION`. Use monkeypatches, fakes, or small test repositories for data-access dependent behavior.

## Syntax/Import Validation

Run syntax/import validation with:

```bash
python -m compileall app.py data_access tests
```

## Regression Rule

For production bugs and risky changes, follow this sequence:

```text
Bug -> regression test -> fix -> test pass
```

Existing strange legacy behavior should first be documented by a test before being intentionally changed.
