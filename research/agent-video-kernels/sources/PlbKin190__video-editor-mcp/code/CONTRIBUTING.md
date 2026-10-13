# Contributing

Contributions are welcome through focused issues and pull requests.

Before submitting:

1. Keep the server local, stdio-only, and independent of external services.
2. Do not add raw command arguments or shell execution. Extend typed schemas and server-owned argument builders instead.
3. Preserve workspace confinement and no-overwrite publication.
4. Add tests for every new validation or security boundary.
5. Run `npm run build` and `npm test` with Node.js 22 and ffmpeg installed.
6. Keep documentation in clear English and avoid committing generated media, credentials, or local paths.

By contributing, you agree that your contribution is licensed under Apache-2.0.
