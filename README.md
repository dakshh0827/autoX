---
title: AutoX
emoji: 🦀
colorFrom: yellow
colorTo: pink
sdk: docker
pinned: false
---

Check out the configuration reference at https://huggingface.co/docs/hub/spaces-config-reference

## Authentication for real users

This app now uses request-provided session data. Each user supplies their own
base64-encoded Playwright `storage_state`, and the backend uses that session to
run headless.

### Create a session locally

1. Run the helper in headful mode:

```bash
python tools/save_storage_state.py
```

2. Complete the X/Twitter login in the browser.
3. Copy the generated `storage_state.json` and base64-encode it.

### Send the session with a request

Send the encoded state in `auth_storage_state_b64`:

```json
{
	"topic": "Renewable energy in India",
	"auth_storage_state_b64": "<base64-encoded-storage-state>"
}
```

If you deploy on Hugging Face Spaces, you can store the same value as a secret
named `STORAGE_STATE_B64` or pass it per request as shown above.

### Important

- Keep `BROWSER_HEADLESS=true` in Spaces.
- Do not commit your storage state to the repo.
- Each real user should use their own login/session data.
