# Phone pairing file — structure note (sample only, no real token)

The bridge never stores a pairing token itself. It stores only a
SHA-256 hash, in a JSON file **outside the repository**, by default:

`~/.config/ai-memory/phone-pairing.json`

The path can be changed with the `PHONE_PAIRING_FILE` environment
variable. The file is created during the founder-only pairing ceremony
(a gated production step), never by this local build, and this note
contains no real credential.

Expected structure (single device):

```json
{
  "device_name": "founder-android",
  "token_sha256": "<64 lowercase hex characters: SHA-256 of the per-device pairing token>"
}
```

Also accepted (several paired devices):

```json
{
  "devices": [
    { "name": "founder-android", "token_sha256": "<64 hex characters>" },
    { "name": "founder-tablet", "token_sha256": "<64 hex characters>" }
  ]
}
```

The phone presents the raw token in the `X-Pairing-Token` header. The
bridge hashes what it receives and compares digests with
`hmac.compare_digest`. No match — or no header — means `401`.

Revocation: remove the device's hash from the file (or delete the
file) and restart the bridge. The presence dies at once.
