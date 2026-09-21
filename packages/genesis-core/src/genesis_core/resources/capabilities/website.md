# Capability: the website

What this is: keeping a business or personal website current. Pages and copy,
product listings and what is in stock, prices (with their hand), photos, opening
hours, a booking page, a newsletter sign-up. The site is the public face; every
change here is one the public will see, so the rules under "Anything the public
will see" in your manual apply to all of it.

## Before the first time

1. Ask which platform the site runs on and who owns the login. You will see the
   answer in the page source too (`wixstatic`, `squarespace`, `wp-content`).
2. Ask what they change most often. That is the first thing to make easy;
   everything else can wait until it is needed.
3. Ask whether any change is routine enough for a standing rule ("you may update
   stock counts yourself"). Write it in this file, dated, in their words. Until
   a rule is written here, every change is draft, show, publish on their word.

## Wix (verified 2026-09-21 against dev.wix.com)

Wix runs an official, hosted MCP server, so an agentic harness can read and
change the site directly, with the person signing in through the browser and
you never holding a password.

If this home was set up with the website capability, Claude Code already has
the server: `<home>/.mcp.json` names `wix` as a remote HTTP server
(`https://mcp.wix.com/mcp`), no Node.js needed. Claude Code asks the person to
approve project servers the first time; that is the consent step, let them read
it. If it is missing, add it to `<home>/.mcp.json` yourself:

```json
{ "mcpServers": { "wix": { "type": "http", "url": "https://mcp.wix.com/mcp" } } }
```

For a harness without remote MCP (needs Node.js 19.9 or newer):

```json
{ "mcpServers": { "wix-mcp-remote": { "command": "npx", "args": ["-y", "@wix/mcp-remote@latest", "https://mcp.wix.com/mcp"] } } }
```

The first call opens a Wix sign-in in the browser; the person signs in as the
site owner. Tools you then have (names as Wix ships them): `ListWixSites`,
`GetSiteContext`, `CallWixSiteAPI` and `ExecuteWixAPI` for site data (Stores
catalog and inventory, Bookings, CMS, events), `ManageWixSite` for publishing,
`UploadImageToWixSite`, and the documentation search tools. Call `WixREADME`
first for any task; it routes you to the right recipe. If the connection dies
after a long idle or an account switch, delete `~/.mcp-auth` (Windows:
`C:\Users\<name>\.mcp-auth`) and sign in again.

Wix API keys (the header-authenticated form) exist for automation tools. Do not
use one unless the person has set one up themselves; it is a credential, and
the browser sign-in makes it unnecessary here.

Typical first-week jobs on Wix: mark products in or out of stock (Stores
inventory), add or edit a product (draft it, show it, publish on their word),
update opening hours or a page's text, check what a Bookings service currently
offers. "Update stock counts" is the canonical candidate for a standing rule;
"change a price" never is.

## Other platforms

Squarespace, WordPress, Shopify, GoDaddy and the rest: use the harness's browser
tool with the person signed in, and do the change where they can see it. If a
platform ships an official MCP server or CLI, verify it against the platform's
own current documentation before recommending it; do not guess from memory.

## Always

- Read a page before you change it; quote the current text back when you
  propose the new one.
- One change, shown, then published. A batch is fine when they asked for the
  batch.
- After publishing, open the live page and confirm the change is there. "Saved"
  is not "live".
- Keep a short log in this file: date, what changed, whose word it was on.

## Standing rules (dated, in their words; empty until they give one)

(none yet)

## Log

(empty)
