# Connecting Wix (verified 2026-09-21 against dev.wix.com and code.claude.com)

Wix runs an official hosted MCP server at `https://mcp.wix.com/mcp`. With it,
the harness can read and change the site directly: products and what is in
stock, bookings, pages, images, and publishing. The person signs in to Wix in
their own browser; you never hold a password. No extra software is needed on
their computer.

## If this home was set up with Wix named

Claude Code already knows the server: `<home>/.mcp.json` names `wix`. The first
time it is used, Claude Code asks the person to approve the project's servers.
That is the consent step; let them read it and say yes. Then the first Wix call
opens a Wix sign-in page in the browser.

## If it is not there yet

Ask the harness to add a remote HTTP MCP server named `wix` at
`https://mcp.wix.com/mcp`, or add it to `<home>/.mcp.json` yourself:

```json
{ "mcpServers": { "wix": { "type": "http", "url": "https://mcp.wix.com/mcp" } } }
```

Then start a new session so the harness picks it up.

## The walkthrough, one step per message

1. "I'm going to connect to your Wix site now. A page will open asking you to
   sign in to Wix. That part is yours; use the same email and password you use
   for Wix. Tell me when you're signed in."
2. If Wix asks which account or site: "Choose the one your website is on."
3. Once signed in, do one read-only thing together: call `WixREADME` first,
   then `ListWixSites` and `GetSiteContext`, and tell them in plain words what
   you can see ("I can see the site, its shop with N products, and the booking
   page"). Seeing before changing.
4. Ask what they would like first. Reading stock, reading upcoming bookings,
   or reading a page's text are all good first jobs. A change waits for their
   word for that item.

## Tools you will have (names as Wix ships them)

`WixREADME` (call first; it routes to the right recipe), `ListWixSites`,
`GetSiteContext`, `CallWixSiteAPI` and `ExecuteWixAPI` (site data: Stores
catalog and inventory, Bookings, CMS, events), `ManageWixSite` (account-level,
including publish), `UploadImageToWixSite`, and the documentation search
tools. If the connection dies after a long idle or an account switch, delete
`~/.mcp-auth` (Windows: `C:\Users\<name>\.mcp-auth`) and sign in again.

## Rules that apply here

- Stock counts and availability are the natural first standing rule ("you may
  update stock counts yourself"); prices never are.
- After publishing anything, open the live page and confirm. "Saved" is not
  "live".
- Wix API keys exist for automation tools. Do not use one unless the person set
  it up themselves; the browser sign-in makes it unnecessary here.
