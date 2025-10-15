# Stoplight Migrator

This repository now includes a Python-based CLI for converting Stoplight documentation to [Fern](https://buildwithfern.com/) docs. The tool reads a Stoplight project's table of contents and markdown pages, then produces the matching markdown files and navigation entries inside `docs.yml`.

## Usage

```bash
PYTHONPATH=src python -m stoplight_migrator.cli <source> --docs-yml docs.yml --docs-root docs
```

- `<source>` can either be a path to a local Stoplight export (containing a `table_of_contents.json` file) or a hosted Stoplight docs URL.
- Generated markdown files are written to `<docs-root>/pages` by default.
- Use `--append-navigation` to append the generated navigation instead of replacing the existing section.
- Pass `--dry-run` to preview the updated `docs.yml` without writing files.

Run the test suite with:

```bash
pytest
```
