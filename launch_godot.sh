#!/usr/bin/env bash
cd "$(dirname "$0")"

CACHE_FILE=".godot_path.txt"
GODOT_BIN=""

if [ -f "$CACHE_FILE" ]; then
    cached="$(cat "$CACHE_FILE")"
    [ -x "$cached" ] && GODOT_BIN="$cached"
fi

if [ -z "$GODOT_BIN" ]; then
    if command -v godot >/dev/null 2>&1; then
        GODOT_BIN=godot
    elif command -v godot4 >/dev/null 2>&1; then
        GODOT_BIN=godot4
    elif [ -x ./godot ]; then
        GODOT_BIN=./godot
    elif [ -x "/Applications/Godot.app/Contents/MacOS/Godot" ]; then
        GODOT_BIN="/Applications/Godot.app/Contents/MacOS/Godot"
    fi
fi

if [ -z "$GODOT_BIN" ]; then
    echo "Searching ~/Desktop, ~/Downloads, and ~/Applications for Godot - one-time search, remembered for next time..."
    for dir in . "$HOME/Desktop" "$HOME/Downloads" "$HOME/Applications" /Applications; do
        [ -d "$dir" ] || continue
        found="$(find "$dir" -maxdepth 4 -iname "Godot*" -type f -perm -u+x 2>/dev/null | head -1)"
        if [ -n "$found" ]; then
            GODOT_BIN="$found"
            break
        fi
        # a .app bundle on macOS isn't itself executable at this path - its MacOS/Godot binary is
        app="$(find "$dir" -maxdepth 4 -iname "Godot*.app" -type d 2>/dev/null | head -1)"
        if [ -n "$app" ] && [ -x "$app/Contents/MacOS/Godot" ]; then
            GODOT_BIN="$app/Contents/MacOS/Godot"
            break
        fi
    done
fi

if [ -z "$GODOT_BIN" ]; then
    echo "Godot 4.3+ wasn't found."
    echo "Either put its full path into a new file '$CACHE_FILE' in this folder,"
    echo "place the binary here as ./godot, or add it to PATH as 'godot'."
    echo "Download it from https://godotengine.org/download if you don't have it yet."
    exit 1
fi

echo "$GODOT_BIN" > "$CACHE_FILE"
echo "Launching Kiara in Godot ($GODOT_BIN)..."
"$GODOT_BIN" --path godot
