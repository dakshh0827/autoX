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

This app now logs into X using the user's username and password. The backend
opens the landing page, clicks the sign-in button, fills the login form, and
then runs the agent with the authenticated browser session.

### Run with credentials

Send the login details directly in the request:

```json
{
	"topic": "Renewable energy in India",
	"username": "your-handle-or-email",
	"password": "your-password"
}
```

If X requires a verification code, include `two_factor_code` or `backup_code`.

### Background mode

The `/api/v1/auth-run` endpoint performs the same login flow and then queues the
agent in the background.

### Important

- Keep `BROWSER_HEADLESS=true` in Spaces.
- Do not commit user credentials to the repo.
- Each real user should use their own login details.
