# Open Proxy Electron

A minimal Electron application for discovering, configuring, starting and stopping local proxy cores.

## MVP features

- Discover cores from `cores/<core-id>/core.json`
- Keep profiles inside each core's `config` directory
- Select a core and profile from the UI
- Edit a profile using a JSON text editor
- Edit the first inbound and basic user settings through a form
- Create, save and delete profiles
- Start and stop one core process
- Display standard output and error logs
- Secure renderer bridge through Electron preload and IPC

## Run

```bash
npm install
npm run dev
```

## Core directory format

```text
cores/
└── sing-box/
    ├── core.json
    ├── bin/
    │   └── sing-box
    └── config/
        └── default.json
```

Example `core.json`:

```json
{
  "name": "sing-box",
  "executable": "bin/sing-box",
  "startArgs": ["run", "-c", "{config}"]
}
```

The repository includes an `example` descriptor and profile, but not a proxy binary. Replace it with a real core directory and make the executable runnable on Linux:

```bash
chmod +x cores/sing-box/bin/sing-box
```

## Current scope

This version deliberately manages only one running core and exposes a small configuration surface. Subscription management, system proxy settings, routing rules, multiple inbounds, tray support and packaging can be added later without replacing the core manager architecture.
