#!/usr/bin/env bash
cd "$(dirname "$0")"

GODOT_BIN=""
if command -v godot >/dev/null 2>&1; then
    GODOT_BIN=godot
elif command -v godot4 >/dev/null 2>&1; then
    GODOT_BIN=godot4
elif [ -x ./godot ]; then
    GODOT_BIN=./godot
fi

if [ -z "$GODOT_BIN" ]; then
    echo "Godot 4.3+ wasn't found."
    echo "Download it from https://godotengine.org/download, then either add it to PATH"
    echo "as 'godot', or place the binary in this folder as ./godot."
    exit 1
fi

echo "Launching Kiara in Godot..."
"$GODOT_BIN" --path godot
