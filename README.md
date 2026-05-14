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

This app now supports a temporary login UI. Each user enters their own
credentials, the backend authenticates headlessly, and then the real work runs
in the background.

### UI flow

1. Open `/auth`.
2. Enter topic, username/email, and password.
3. If X asks for 2FA, enter the verification or backup code.
4. After login succeeds, the UI closes and the backend job keeps running.

### API flow

If you want to call the API directly, send a request to `/auth-run` with the
same fields. The backend will authenticate, save a temporary session, and start
the job in headless mode.

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

If you deploy on Hugging Face Spaces, store the same value as a secret named
`STORAGE_STATE_B64` or pass it per request as shown above.

### Important

- Keep `BROWSER_HEADLESS=true` in Spaces.
- Do not commit your storage state to the repo.
- Each real user should use their own login/session data.
