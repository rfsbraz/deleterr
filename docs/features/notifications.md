# Notifications

Deleterr supports multiple notification providers to keep you and your users informed about media cleanup activities.

## Two Types of Notifications

Deleterr sends two distinct types of notifications:

| Type | Purpose | Audience |
|------|---------|----------|
| **Run Summary** | What was deleted this run | Admins |
| **Leaving Soon** | What's scheduled for deletion | Users |

## Quick Start

### Admin Notifications (Run Summary)

Receive alerts when Deleterr deletes media:

=== "Discord"

    ```yaml
    notifications:
      enabled: true
      discord:
        webhook_url: "https://discord.com/api/webhooks/..."
    ```

=== "Slack"

    ```yaml
    notifications:
      enabled: true
      slack:
        webhook_url: "https://hooks.slack.com/services/..."
    ```

=== "Telegram"

    ```yaml
    notifications:
      enabled: true
      telegram:
        bot_token: "123456789:ABCdefGHI..."
        chat_id: "-1001234567890"
    ```

=== "Email"

    ```yaml
    notifications:
      enabled: true
      email:
        smtp_server: "smtp.gmail.com"
        smtp_port: 587
        smtp_username: !env SMTP_USERNAME
        smtp_password: !env SMTP_PASSWORD
        use_tls: true
        from_address: "deleterr@yourdomain.com"
        to_addresses:
          - "admin@yourdomain.com"
    ```

### User Notifications (Leaving Soon)

Alert users about content they should watch before it's deleted:

```yaml
notifications:
  leaving_soon:
    subject: "Content leaving your Plex server soon!"
    email:
      smtp_server: "smtp.gmail.com"
      smtp_port: 587
      smtp_username: !env SMTP_USERNAME
      smtp_password: !env SMTP_PASSWORD
      use_tls: true
      from_address: "plex@yourdomain.com"
      to_addresses:
        - "family@example.com"
        - "friends@example.com"
```

!!! note "Separate Configuration"
    Leaving Soon notifications are configured separately from run summary notifications. They do NOT inherit provider settings from the parent config.

## Provider Configuration

### Discord

Send rich embeds to Discord channels via webhooks.

```yaml
notifications:
  discord:
    webhook_url: "https://discord.com/api/webhooks/..."
    username: "Deleterr"
    avatar_url: "https://example.com/avatar.png"
```

| Property | Required | Description |
|----------|----------|-------------|
| `webhook_url` | Yes | Discord webhook URL |
| `username` | No | Bot username override |
| `avatar_url` | No | Bot avatar URL |

**Creating a webhook:**

1. Open Discord channel settings
2. Go to Integrations > Webhooks
3. Click "New Webhook"
4. Copy the webhook URL

### Slack

Send messages to Slack via Incoming Webhooks.

```yaml
notifications:
  slack:
    webhook_url: "https://hooks.slack.com/services/..."
    channel: "#media-cleanup"
    username: "Deleterr"
    icon_emoji: ":wastebasket:"
```

| Property | Required | Description |
|----------|----------|-------------|
| `webhook_url` | Yes | Slack webhook URL |
| `channel` | No | Override target channel |
| `username` | No | Bot username override |
| `icon_emoji` | No | Bot icon emoji |

### Telegram

Send messages via the Telegram Bot API.

```yaml
notifications:
  telegram:
    bot_token: "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
    chat_id: "-1001234567890"
    parse_mode: "MarkdownV2"
```

| Property | Required | Description |
|----------|----------|-------------|
| `bot_token` | Yes | Bot token from @BotFather |
| `chat_id` | Yes | Target chat/group/channel ID |
| `parse_mode` | No | Message format (default: MarkdownV2) |

**Getting your chat ID:**

1. Add your bot to the group/channel
2. Send a message to the group
3. Visit `https://api.telegram.org/bot<TOKEN>/getUpdates`
4. Find the `chat.id` value

### Email

Send HTML emails via SMTP.

```yaml
notifications:
  email:
    smtp_server: "smtp.gmail.com"
    smtp_port: 587
    smtp_username: !env SMTP_USERNAME
    smtp_password: !env SMTP_PASSWORD
    use_tls: true
    from_address: "deleterr@yourdomain.com"
    to_addresses:
      - "admin@yourdomain.com"
    subject: "Deleterr Run Complete"
```

| Property | Required | Default | Description |
|----------|----------|---------|-------------|
| `smtp_server` | Yes | - | SMTP server hostname |
| `smtp_port` | Yes | - | SMTP port (587 for TLS, 465 for SSL) |
| `smtp_username` | Yes | - | SMTP authentication username |
| `smtp_password` | Yes | - | SMTP authentication password |
| `use_tls` | No | `true` | Enable STARTTLS |
| `from_address` | Yes | - | Sender email address |
| `to_addresses` | Yes | - | List of recipient addresses |
| `subject` | No | - | Email subject line |

#### Gmail Setup

1. Enable [2-Step Verification](https://myaccount.google.com/signinoptions/two-step-verification)
2. Create an [App Password](https://myaccount.google.com/apppasswords)
3. Use the app password as `smtp_password`

### Webhook (Generic)

Send JSON payloads to any HTTP endpoint.

```yaml
notifications:
  webhook:
    url: "https://example.com/webhook"
    method: "POST"
    headers:
      Authorization: "Bearer your-token"
      Content-Type: "application/json"
    timeout: 30
```

| Property | Required | Default | Description |
|----------|----------|---------|-------------|
| `url` | Yes | - | Webhook endpoint URL |
| `method` | No | `POST` | HTTP method |
| `headers` | No | - | Custom HTTP headers |
| `timeout` | No | `30` | Request timeout in seconds |

## General Settings

```yaml
notifications:
  enabled: true
  notify_on_dry_run: true
  include_preview: true
  min_deletions_to_notify: 1
```

| Property | Default | Description |
|----------|---------|-------------|
| `enabled` | `true` | Enable/disable all notifications |
| `notify_on_dry_run` | `true` | Send notifications during dry runs |
| `include_preview` | `true` | Include preview of items in notification |
| `min_deletions_to_notify` | `1` | Minimum deletions to trigger notification |

## Leaving Soon Templates

The default leaving soon template includes:

- Warning explaining items will be removed
- Tip explaining how watching content keeps it
- Grouped sections for Movies and TV Shows
- Links to Plex (if configured)
- Links to Overseerr for re-requesting (if configured)

### Custom Templates

Use your own HTML template:

```yaml
notifications:
  leaving_soon:
    template: "/config/my-template.html"
    subject: "Watch Before It's Gone!"
    email:
      # ... email settings
```

Template variables available:

| Variable | Description |
|----------|-------------|
| `{{ movies }}` | List of movie items |
| `{{ shows }}` | List of TV show items |
| `{{ plex_url }}` | Plex server URL (if configured) |
| `{{ overseerr_url }}` | Overseerr URL (if configured) |

## Testing Notifications

Test your configuration before relying on it:

```bash
# Test leaving_soon notifications (default)
docker run --rm -v ./config:/config deleterr \
  python -m scripts.test_notifications

# Test run summary notifications
docker run --rm -v ./config:/config deleterr \
  python -m scripts.test_notifications --type run_summary

# Test specific provider only
docker run --rm -v ./config:/config deleterr \
  python -m scripts.test_notifications --provider email

# Preview without sending (dry run)
docker run --rm -v ./config:/config deleterr \
  python -m scripts.test_notifications --dry-run

# Show configuration status
docker run --rm -v ./config:/config deleterr \
  python -m scripts.test_notifications --status
```

## Multiple Providers

Use multiple providers simultaneously:

```yaml
notifications:
  enabled: true
  # Admin gets Discord + Email
  discord:
    webhook_url: !env DISCORD_ADMIN_WEBHOOK
  email:
    smtp_server: "smtp.gmail.com"
    # ... email settings
    to_addresses:
      - "admin@example.com"

  # Users get separate notifications
  leaving_soon:
    discord:
      webhook_url: !env DISCORD_USERS_WEBHOOK
    email:
      smtp_server: "smtp.gmail.com"
      # ... email settings
      to_addresses:
        - "users@example.com"
```

## Troubleshooting

### Notifications Not Sending

1. **Check enabled flag**: Ensure `notifications.enabled: true`
2. **Verify credentials**: Test API keys/tokens manually
3. **Check logs**: Look for notification errors in Deleterr logs
4. **Test configuration**: Run the test script

### Discord Webhook Errors

- **401 Unauthorized**: Webhook URL is invalid or deleted
- **400 Bad Request**: Message format issue (check logs)
- **429 Rate Limited**: Too many requests, Deleterr will retry

### Email Not Arriving

1. Check spam/junk folders
2. Verify SMTP credentials
3. For Gmail, ensure App Password is used (not account password)
4. Check `use_tls` matches your SMTP port (587=TLS, 465=SSL)

### Telegram Bot Not Responding

1. Verify bot token with @BotFather
2. Ensure bot is added to the target chat
3. For groups, bot must be admin or have message permissions
4. Check chat_id is correct (use getUpdates API)
