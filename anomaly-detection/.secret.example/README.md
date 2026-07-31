# Secret file templates

Copy only the files needed by your workshop mode to `../.secret/`, remove the
`.example` suffix, and replace the placeholder text. Secret files contain one
value with no YAML key or quotes.

- `license.example` is required in local and Cloud modes.
- `ANTHROPIC_API_KEY.example` is optional. When present as
  `.secret/ANTHROPIC_API_KEY`, `up.sh` enables the vmanomaly UI Copilot with
  `anthropic:claude-sonnet-5`.
- The remaining files are required only for Cloud mode.

Never commit the populated `.secret/` directory.
