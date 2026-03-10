#!/usr/bin/env bash
set -e
SRC="$(cd "$(dirname "$0")" && pwd)"
TARGET="${HOME}/.local/share/gxostx6"
BIN="${HOME}/.local/bin"
mkdir -p "$TARGET" "$BIN"
cp -f "${SRC}/gxost.py" "${SRC}/gxost.x6.py" "${SRC}/README.md" "$TARGET"/
echo -e "#!/usr/bin/env bash\npython \"${TARGET}/gxost.x6.py\" \"\$@\"" > "${BIN}/gxost-x6"
chmod +x "${BIN}/gxost-x6"
echo "Installed to ${TARGET}"
echo "Ensure ${HOME}/.local/bin is in PATH. Then run: gxost-x6 --help"
