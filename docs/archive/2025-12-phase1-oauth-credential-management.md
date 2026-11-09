# OAuth Credential Management

This document describes how the karaoke-gen backend manages OAuth credentials for YouTube, Google Drive, and Dropbox services.

## Overview

The backend needs OAuth credentials to:
- **YouTube**: Upload karaoke videos to your channel
- **Google Drive**: Upload files to public share folders
- **Dropbox**: Organize output files into brand-coded folders

OAuth tokens have limited lifespans and occasionally need re-authorization (e.g., when Google requires re-consent). This system provides:

1. **Proactive Monitoring**: Validates credentials on startup and alerts via Discord
2. **Pre-job Validation**: Rejects jobs if required credentials are invalid
3. **Device Authorization Flow**: Re-authenticate from any device without browser access on the server

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Credential Flow                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────────────────────┐   │
│  │   Secrets   │────►│  Backend    │────►│   External Services         │   │
│  │   Manager   │     │   API       │     │   (YouTube/GDrive/Dropbox)  │   │
│  └─────────────┘     └─────────────┘     └─────────────────────────────┘   │
│        ▲                    │                                                │
│        │                    │ If invalid                                     │
│        │                    ▼                                                │
│        │             ┌─────────────┐                                        │
│        │             │   Discord   │                                        │
│        │             │   Alert     │                                        │
│        │             └─────────────┘                                        │
│        │                    │                                                │
│        │                    ▼                                                │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────────────────────┐   │
│  │   Update    │◄────│   Device    │◄────│   Admin authorizes on       │   │
│  │   Secret    │     │   Auth      │     │   google.com/device         │   │
│  └─────────────┘     │   Flow      │     └─────────────────────────────┘   │
│                      └─────────────┘                                        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Secrets in GCP Secret Manager

The following secrets store OAuth credentials:

| Secret Name | Service | Contents |
|-------------|---------|----------|
| `youtube-oauth-credentials` | YouTube | OAuth tokens with `youtube` scope |
| `youtube-client-credentials` | YouTube | OAuth client ID and secret for device auth |
| `gdrive-oauth-credentials` | Google Drive | OAuth tokens with `drive.file` scope |
| `gdrive-client-credentials` | Google Drive | OAuth client ID and secret for device auth |
| `dropbox-oauth-credentials` | Dropbox | OAuth tokens with app key/secret |
| `discord-alert-webhook` | Discord | Webhook URL for credential alerts |

### YouTube/Google Drive OAuth Token Format

```json
{
  "token": "ya29.xxxxx...",
  "refresh_token": "1//xxxxx...",
  "client_id": "123456789-xxxxx.apps.googleusercontent.com",
  "client_secret": "GOCSPX-xxxxx",
  "token_uri": "https://oauth2.googleapis.com/token",
  "scopes": ["https://www.googleapis.com/auth/youtube"]
}
```

### YouTube/Google Drive Client Credentials Format

These are used for the device authorization flow:

```json
{
  "client_id": "123456789-xxxxx.apps.googleusercontent.com",
  "client_secret": "GOCSPX-xxxxx"
}
```

### Dropbox Credential Format

```json
{
  "access_token": "sl.xxxxx...",
  "refresh_token": "xxxxx...",
  "app_key": "xxxxx",
  "app_secret": "xxxxx"
}
```

## API Endpoints

### Check Credential Status

```bash
# Check all credentials
GET /api/auth/status

# Response
{
  "youtube": {
    "service": "youtube",
    "status": "valid",
    "message": "YouTube credentials are valid",
    "last_checked": "2024-01-15T10:30:00Z"
  },
  "gdrive": {
    "service": "gdrive",
    "status": "invalid",
    "message": "Token refresh failed",
    "last_checked": "2024-01-15T10:30:00Z"
  },
  "dropbox": {
    "service": "dropbox",
    "status": "valid",
    "message": "Dropbox credentials are valid",
    "last_checked": "2024-01-15T10:30:00Z"
  },
  "all_valid": false,
  "services_needing_auth": ["gdrive"]
}
```

### Validate Credentials Before Job

```bash
# Validate specific services
POST /api/auth/validate
{
  "youtube": true,
  "gdrive": true,
  "dropbox": false
}

# Response (if valid)
{
  "valid": true,
  "invalid_services": [],
  "message": "All requested credentials are valid"
}

# Response (if invalid)
{
  "valid": false,
  "invalid_services": ["gdrive"],
  "message": "The following services need re-authorization: gdrive"
}
```

### Device Authorization Flow

The device flow allows re-authorization without browser access on the server.

**Step 1: Start the flow**

```bash
# Client credentials are loaded from Secret Manager automatically
POST /api/auth/youtube/device

# Or explicitly provide credentials (optional)
POST /api/auth/youtube/device
{
  "client_id": "123456789-xxxxx.apps.googleusercontent.com",
  "client_secret": "GOCSPX-xxxxx"
}

# Response
{
  "device_code": "AH-1Ng...",
  "user_code": "WXYZ-ABCD",
  "verification_url": "https://www.google.com/device",
  "expires_in": 1800,
  "interval": 5,
  "instructions": "Visit https://www.google.com/device and enter code: WXYZ-ABCD"
}
```

**Step 2: User visits URL and enters code**

The admin visits `https://www.google.com/device` on any device and enters the user code.

**Step 3: Poll for completion**

```bash
GET /api/auth/youtube/device/{device_code}

# Response while waiting
{
  "status": "pending",
  "message": null,
  "credentials_saved": false
}

# Response on success
{
  "status": "complete",
  "message": null,
  "credentials_saved": true
}

# Response on expiry
{
  "status": "expired",
  "message": null,
  "credentials_saved": false
}
```

## Job Submission Validation

When a job is submitted with distribution features enabled, the API validates that required credentials are available:

```bash
POST /api/jobs/upload
  --enable_youtube_upload=true  # Requires valid YouTube credentials
  --dropbox_path=/Karaoke/...   # Requires valid Dropbox credentials
  --gdrive_folder_id=xxxxx      # Requires valid Google Drive credentials

# If credentials are invalid:
HTTP 400
{
  "error": "credentials_invalid",
  "message": "The following distribution services need re-authorization: youtube (Token refresh failed)",
  "invalid_services": ["youtube (Token refresh failed)"],
  "auth_url": "/api/auth/status"
}
```

## Startup Validation & Alerts

On backend startup:

1. All OAuth credentials are validated
2. Token refresh is attempted for expired tokens
3. If any credentials are invalid, a Discord alert is sent

### Discord Alert Format

```
⚠️ OAuth Credentials Need Attention

The following service credentials need re-authorization:

• youtube: Token refresh failed
• gdrive: Missing required fields: [client_secret]

Re-authorize:
Visit https://your-api-url/api/auth/status to start re-authorization flow
```

## Setting Up Credentials Initially

### From rclone Config (Dropbox/Google Drive)

If you have working rclone remotes, extract credentials:

```bash
# View rclone config
cat ~/.config/rclone/rclone.conf

# Extract Dropbox section and create secret
gcloud secrets create dropbox-oauth-credentials --project=your-project
gcloud secrets versions add dropbox-oauth-credentials --data-file=dropbox-creds.json

# Extract Google Drive section and create secret  
gcloud secrets create gdrive-oauth-credentials --project=your-project
gcloud secrets versions add gdrive-oauth-credentials --data-file=gdrive-creds.json
```

### Via Device Authorization Flow

For YouTube (or any Google service):

1. Get your OAuth client ID and secret from Google Cloud Console
2. Call `POST /api/auth/youtube/device` with credentials
3. Visit the verification URL and authorize
4. Poll until completion - credentials are automatically saved

## Re-authorization Flow

When credentials expire:

1. **Automatic Alert**: Backend sends Discord notification on startup
2. **Job Rejection**: Jobs requiring invalid credentials are rejected
3. **Re-auth**: Admin uses device flow to get new tokens
4. **Resume**: Jobs can be submitted again

### Using Device Flow for Re-auth

```bash
# 1. Get OAuth client credentials (same ones used originally)
CLIENT_ID="your-client-id"
CLIENT_SECRET="your-client-secret"

# 2. Start device flow
curl -X POST https://your-api/api/auth/youtube/device \
  -H "Content-Type: application/json" \
  -d "{\"client_id\": \"$CLIENT_ID\", \"client_secret\": \"$CLIENT_SECRET\"}"

# 3. Visit URL and enter code shown in response

# 4. Poll until complete
curl https://your-api/api/auth/youtube/device/{device_code}
```

## Credential Status Values

| Status | Meaning |
|--------|---------|
| `valid` | Credentials work and token is fresh |
| `expired` | Token expired but refresh may work |
| `invalid` | Refresh failed, re-authorization needed |
| `not_configured` | No credentials in Secret Manager |
| `error` | Unknown error during validation |

## Security Considerations

1. **Secret Manager**: All credentials are stored in GCP Secret Manager, not in code or config files

2. **Token Refresh**: Access tokens are refreshed automatically; only refresh tokens need occasional re-auth

3. **Scope Limitation**: 
   - YouTube: `youtube` scope (video upload only)
   - Google Drive: `drive.file` scope (access only to files created by the app)
   - Dropbox: App folder or full access depending on app configuration

4. **No Client Secrets in Frontend**: Device flow client secrets are provided via API, not hardcoded

5. **Alert Webhook**: The Discord webhook for alerts should be stored in Secret Manager as `discord-alert-webhook`

## Future Improvements

- [ ] Email alerts in addition to Discord
- [ ] Web UI for credential status and re-auth
- [ ] Scheduled periodic validation (Cloud Scheduler)
- [ ] Admin authentication for auth endpoints
- [ ] Support for multiple YouTube channels
