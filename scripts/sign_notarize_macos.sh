#!/usr/bin/env bash
set -euo pipefail

if [[ ${TRACE:-0} -eq 1 ]]; then
  set -x
fi

APP_PATH=${APP_PATH:-dist/JointSpaceVisualizer.app}
DMG_OUTPUT=${DMG_OUTPUT:-installer/macos/JointSpaceVisualizer-mac.signed.dmg}
VOL_NAME=${VOL_NAME:-JointSpaceVisualizer}
IDENTITY=${CODESIGN_IDENTITY:-}
NOTARY_PROFILE=${NOTARYTOOL_PROFILE:-}
TEAM_ID=${TEAM_ID:-}

usage() {
  cat <<'USAGE'
Usage: CODESIGN_IDENTITY="Developer ID Application: Example" NOTARYTOOL_PROFILE="notarytool-profile" TEAM_ID="ABCD123456" ./scripts/sign_notarize_macos.sh

Environment variables:
  APP_PATH             Path to the .app bundle you want to sign (default: dist/JointSpaceVisualizer.app)
  DMG_OUTPUT           Output path for the signed DMG (default: installer/macos/JointSpaceVisualizer-mac.signed.dmg)
  VOL_NAME             Volume name to use when creating the DMG (default: JointSpaceVisualizer)
  CODESIGN_IDENTITY    Required. Developer ID Application identity from Keychain (e.g. "Developer ID Application: Your Name (TEAMID)")
  NOTARYTOOL_PROFILE   Required. Keychain profile name created via `xcrun notarytool store-credentials`
  TEAM_ID              Required. Your 10-character Apple Developer Team ID

Set TRACE=1 for verbose execution.
USAGE
}

if [[ -z "$IDENTITY" || -z "$NOTARY_PROFILE" || -z "$TEAM_ID" ]]; then
  usage
  >&2 echo "Missing required environment variables."
  exit 2
fi

if [[ ! -d "$APP_PATH" ]]; then
  >&2 echo "App bundle not found: $APP_PATH"
  exit 3
fi

if ! security find-identity -p codesigning -v | grep -F "$IDENTITY" >/dev/null; then
  >&2 echo "Signing identity not found in keychain: $IDENTITY"
  exit 4
fi

work_dir=$(mktemp -d)
cleanup() {
  rm -rf "$work_dir"
}
trap cleanup EXIT

log() {
  printf '[%s] %s\n' "$(date '+%H:%M:%S')" "$1"
}

sign_target() {
  local target="$1"
  local use_runtime="${2:-1}"
  local args=(--force --timestamp --sign "$IDENTITY")
  if [[ "$use_runtime" == "1" ]]; then
    args+=(--options runtime)
  fi
  log "codesign: $target"
  codesign "${args[@]}" "$target"
}

log "Clearing extended attributes"
xattr -cr "$APP_PATH"

log "Signing embedded frameworks"
find "$APP_PATH" -type d -name '*.framework' -print0 \
  | while IFS= read -r -d '' framework; do
      sign_target "$framework"
    done

log "Signing dynamic libraries and executables"
find "$APP_PATH" \( -type f -perm -111 -o -name '*.dylib' -o -name '*.so' -o -name '*.pyd' \) -print0 \
  | while IFS= read -r -d '' binary; do
      sign_target "$binary"
    done

log "Signing main executable"
sign_target "$APP_PATH/Contents/MacOS/JointSpaceVisualizer"

log "Signing top-level app bundle"
sign_target "$APP_PATH"

log "Verifying code signature"
codesign --verify --deep --strict --verbose=2 "$APP_PATH"

log "Creating DMG"
unsigned_dmg="$work_dir/unsigned.dmg"
rm -f "$DMG_OUTPUT"
hdiutil create -fs HFS+ -volname "$VOL_NAME" -srcfolder "$APP_PATH" "$unsigned_dmg" >/dev/null

log "Signing DMG shell"
sign_target "$unsigned_dmg" 0

log "Submitting DMG for notarization"
xcrun notarytool submit "$unsigned_dmg" --keychain-profile "$NOTARY_PROFILE" --team-id "$TEAM_ID" --wait

log "Stapling notarization ticket"
xcrun stapler staple "$APP_PATH"
xcrun stapler staple "$unsigned_dmg"

log "Moving signed DMG to $DMG_OUTPUT"
mkdir -p "$(dirname "$DMG_OUTPUT")"
mv "$unsigned_dmg" "$DMG_OUTPUT"

log "Final Gatekeeper assessment"
spctl --assess --type exec --verbose "$APP_PATH"
spctl --assess --type open --verbose "$DMG_OUTPUT"

log "All done"
