#!/bin/sh
# Genesis installer — macOS / Linux.
#
# Pull-not-push (SOVEREIGNTY.md): you ran this command yourself; it sets up your
# AI on your own machine. The web never touched your computer. The onboarding
# seed (how you want it tuned) rides in the GENESIS_SEED env var that the install
# command set — nothing is fetched from any server but the code itself.
#
# Usage (the web hands you this, with the seed filled in):
#   GENESIS_SEED='<blob>' sh -c "$(curl -fsSL https://<host>/install.sh)"
set -eu

REPO="${GENESIS_REPO:-https://github.com/REPLACE_WITH_PUBLIC_REPO}"
APP_DIR="${GENESIS_APP_DIR:-$HOME/.genesis-app}"
BIN_DIR="${GENESIS_BIN_DIR:-$HOME/.local/bin}"

say() { printf '%s\n' "$*"; }
have() { command -v "$1" >/dev/null 2>&1; }

say "Genesis: setting up your AI's home…"

# 1. prerequisites — both are human-installable, so we explain rather than guess.
if ! have python3; then
  say "Python 3 is required. Install it from https://www.python.org/downloads/ and run this again."
  exit 1
fi
if ! have git; then
  say "git is required. Install it (macOS: 'xcode-select --install'; Linux: your package manager) and run this again."
  exit 1
fi

# 2. fetch the code (shallow; update in place if already there)
# Public repo → no credentials. Disable prompts/helper so a headless run can't
# hang or fail asking for a GitHub username.
export GIT_TERMINAL_PROMPT=0
NOCRED="-c credential.helper= -c credential.interactive=false"
if [ -d "$APP_DIR/.git" ]; then
  say "Updating Genesis in $APP_DIR"
  git $NOCRED -C "$APP_DIR" pull --ff-only || say "  (couldn't fast-forward; keeping what's there)"
else
  say "Downloading Genesis into $APP_DIR"
  if ! git $NOCRED clone --depth 1 "$REPO" "$APP_DIR"; then
    say "Could not download Genesis from $REPO. Check your internet connection and try again."
    exit 1
  fi
fi

# 3. install into a private venv (no sudo, no clobbering system python)
say "Installing…"
python3 -m venv "$APP_DIR/.venv"
VPY="$APP_DIR/.venv/bin/python"
"$VPY" -m pip install -q --upgrade pip
"$VPY" -m pip install -q \
  -e "$APP_DIR/packages/genesis-memory" \
  -e "$APP_DIR/packages/genesis-backend" \
  -e "$APP_DIR/packages/genesis-core"

# 4. a friendly `genesis` shim on PATH
mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/genesis" <<EOF
#!/bin/sh
exec "$APP_DIR/.venv/bin/genesis" "\$@"
EOF
chmod +x "$BIN_DIR/genesis"

# 5. stand up the tuned home. The seed (GENESIS_SEED) is read by init itself.
say "Standing up your AI's home (tuned to your setup answers)…"
"$VPY" -m genesis_core.cli init

say ""
say "Installed. The 'genesis' command is at $BIN_DIR/genesis"
case ":$PATH:" in
  *":$BIN_DIR:"*) : ;;
  *) say "Add it to your PATH:  export PATH=\"$BIN_DIR:\$PATH\"  (add to ~/.zshrc or ~/.bashrc)" ;;
esac
say ""
say "Next — connect a brain:   genesis install"
say "Then start the loops:     genesis schedule install"
say "Talk to it any time:      genesis chat"
