# Vendoring Ketcher (standalone build)

OpenMolClaw embeds a Ketcher build as a plain static bundle in this folder — no
React or Vite build step of your own at *app* runtime. The bridge in
`web/app.js` talks to the standard `window.ketcher` API (`setMolecule`,
`getMolfile`) exposed by that build, so the editor is fully decoupled from the
harness.

Ketcher is licensed under Apache-2.0 by EPAM Systems and is **not** redistributed
inside this repository; you build or fetch it yourself.

## Important: upstream release zips changed shape

As of Ketcher 3.x, the `ketcher-standalone*.zip` assets on the [official
releases page](https://github.com/epam/ketcher/releases) contain only the
`ketcher-standalone` **npm library** (`dist/index.js`, `dist/main.js`, wasm
binaries, etc.) — there is **no `index.html` demo page in the release zip
anymore**. That means:

- `openmolclaw install-ketcher --archive <release-zip-url>` fails with
  `archive did not contain a Ketcher index.html` for any current release.
- To get a real iframe-embeddable page you build the demo yourself from the
  Ketcher monorepo's `example` workspace (Option A below), or bundle the npm
  package into your own tiny HTML/JS wrapper (Option B).

## Option A — build the demo from source (recommended)

Requires Node.js **>= 24** and npm (older Node runs with an engine warning but
has been observed to build successfully). Building the whole monorepo can take
several minutes and a few hundred MB of disk.

```bash
git clone --depth 1 --branch v3.15.0 https://github.com/epam/ketcher.git /tmp/ketcher-src
cd /tmp/ketcher-src
npm install
npm run build:packages
npm run build:example:standalone
```

This produces `example/dist/standalone/index.html` plus its static assets.
Point `install-ketcher` at that build **directory** (no need to zip it — the
command accepts a local directory, a local archive, or an HTTPS URL to an
archive):

```bash
openmolclaw install-ketcher --archive /tmp/ketcher-src/example/dist/standalone
```

## Option B — npm library + your own wrapper page

```bash
npm pack ketcher-standalone
# extract the tarball's dist/ into this folder, then write your own index.html
# that imports it and wires up window.ketcher (see the built example's
# index.html from Option A for a reference implementation).
```

## If you have an older archive

A pre-3.x Ketcher standalone archive that still ships `index.html` + `static/`
works unchanged:

```bash
openmolclaw install-ketcher --archive /path/to/old-ketcher-standalone.zip
```

## Verify

Start the app and open the page:

```bash
openmolclaw serve
# http://127.0.0.1:5000
```

If the editor iframe stays blank and a "Ketcher is not vendored yet" notice
appears, the files above are missing. The SMILES/RDKit tools and workspace still
work without the editor.

> This directory is intentionally empty except for this note; the vendored build
> is git-ignored so the Apache-2.0 Ketcher assets are not committed here.
