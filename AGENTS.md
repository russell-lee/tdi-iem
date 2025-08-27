# Agent Guidelines

## Code Formatting

- Run `make fmt` before committing to format code with Black (line length 100).

## Testing

- Run `make test` to execute the pytest suite and validate changes.

## Project Pipeline & Makefile Targets

- `make build` runs the pipeline of `extract`, `parse`, `repair`, and `emit` steps.
- `make eval` evaluates generated output.
- `scripts/run.sh` provides a convenience wrapper to run the full pipeline end-to-end.

