#!/usr/bin/env bash
set -euo pipefail

# Export draw.io diagrams to SVG and PDF via draw.io desktop CLI,
# then render PNG from PDF via pdftocairo for reliable full-frame output.
# Usage:
#   ./export_drawio.sh
#   DRAWIO_BIN=/path/to/drawio ./export_drawio.sh
#
# Common overrides:
#   PNG_RENDERER=chromium CHROMIUM_SHOTTER=puppeteer ./export_drawio.sh
#   # If headless Chromium renders SVG text differently (font fallback / foreignObject):
#   CHROMIUM_SVG_TEXT_MODE=fallback-images ./export_drawio.sh   # default
#   CHROMIUM_SVG_TEXT_MODE=foreignobject   ./export_drawio.sh   # closer to browser SVG behavior

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FIGURES_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
EXPORT_DIR="${SCRIPT_DIR}/exports"

PNG_PADDING="${PNG_PADDING:-40}"
PNG_DPI="${PNG_DPI:-150}"
PNG_RENDERER="${PNG_RENDERER:-pdf}"  # pdf | chromium | native
CHROMIUM_VIRTUAL_TIME_BUDGET="${CHROMIUM_VIRTUAL_TIME_BUDGET:-2000}"
CHROMIUM_SHOTTER="${CHROMIUM_SHOTTER:-puppeteer}"  # puppeteer | builtin
CHROMIUM_HTML_PADDING="${CHROMIUM_HTML_PADDING:-0}"
CHROMIUM_SVG_TEXT_MODE="${CHROMIUM_SVG_TEXT_MODE:-fallback-images}"  # foreignobject | fallback-images
PUPPETEER_CACHE_DIR="${PUPPETEER_CACHE_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/curaview-puppeteer}"
PUPPETEER_VERSION="${PUPPETEER_VERSION:-24.15.0}"
AUTO_INSTALL_PUPPETEER="${AUTO_INSTALL_PUPPETEER:-1}"

prepare_svg_for_chromium() {
  local in_svg="$1"
  local out_svg="$2"

  case "${CHROMIUM_SVG_TEXT_MODE}" in
    foreignobject)
      cp -f "${in_svg}" "${out_svg}"
      ;;
    fallback-images|*)
      # draw.io exports many labels as <switch><foreignObject .../><image .../></switch>.
      # Headless Chromium font fallback can slightly change metrics and shift labels.
      # Force the <image> fallback by making requiredFeatures impossible to satisfy.
      sed 's|requiredFeatures="http://www.w3.org/TR/SVG11/feature#Extensibility"|requiredFeatures="http://www.w3.org/TR/SVG11/feature#__DISABLED__"|g' \
        "${in_svg}" >"${out_svg}"
      ;;
  esac
}

DRAWIO_BIN="${DRAWIO_BIN:-}"
if [[ -z "${DRAWIO_BIN}" ]]; then
  if command -v drawio >/dev/null 2>&1; then
    DRAWIO_BIN="drawio"
  elif command -v draw.io >/dev/null 2>&1; then
    DRAWIO_BIN="draw.io"
  fi
fi

if [[ -z "${DRAWIO_BIN}" ]]; then
  cat <<'EOF'
Error: draw.io CLI not found.

Install one of these first:
1) draw.io desktop AppImage/deb and ensure command is available.
2) Use Docker image that wraps drawio-desktop headless.

Then run again with:
  DRAWIO_BIN=/path/to/drawio ./export_drawio.sh
EOF
  exit 1
fi

PDFTOCAIRO_BIN=""
if command -v pdftocairo >/dev/null 2>&1; then
  PDFTOCAIRO_BIN="pdftocairo"
fi

CHROMIUM_BIN="${CHROMIUM_BIN:-}"
if [[ -z "${CHROMIUM_BIN}" ]]; then
  if command -v chromium >/dev/null 2>&1; then
    CHROMIUM_BIN="chromium"
  elif command -v chromium-browser >/dev/null 2>&1; then
    CHROMIUM_BIN="chromium-browser"
  elif command -v google-chrome >/dev/null 2>&1; then
    CHROMIUM_BIN="google-chrome"
  fi
fi

render_png_from_svg_with_chromium() {
  local svg_file="$1"
  local out_png="$2"
  local svg_for_render
  local svg_dir
  local svg_name
  local svg_width
  local svg_height
  local window_width
  local window_height
  local tmp_html
  local tmp_svg
  local tmp_profile

  svg_dir="$(cd "$(dirname "${svg_file}")" && pwd)"
  svg_name="$(basename "${svg_file}")"

  tmp_svg="${svg_dir}/.__svgshot_render_$$.svg"
  prepare_svg_for_chromium "${svg_file}" "${tmp_svg}"
  svg_for_render="${tmp_svg}"
  svg_name="$(basename "${svg_for_render}")"

  svg_width="$(sed -n 's/.* width="\([0-9]\+\)px".*/\1/p' "${svg_file}" | head -n1)"
  svg_height="$(sed -n 's/.* height="\([0-9]\+\)px".*/\1/p' "${svg_file}" | head -n1)"

  if [[ -n "${svg_width}" && -n "${svg_height}" ]]; then
    window_width="$((svg_width + 2 * CHROMIUM_HTML_PADDING))"
    window_height="$((svg_height + 2 * CHROMIUM_HTML_PADDING))"
  else
    window_width="1700"
    window_height="1000"
  fi

  tmp_html="${svg_dir}/.__svgshot_tmp_$$.html"
  tmp_profile="$(mktemp -d /tmp/chromium-profile.XXXXXX)"
  cat >"${tmp_html}" <<EOF
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    html, body {
      margin: 0;
      padding: ${CHROMIUM_HTML_PADDING}px;
      overflow: hidden;
      background: #fff;
      box-sizing: border-box;
      width: ${window_width}px;
      height: ${window_height}px;
    }
    img {
      display: block;
      width: ${svg_width}px;
      height: ${svg_height}px;
    }
  </style>
</head>
<body>
  <img src="${svg_name}" alt="diagram">
</body>
</html>
EOF

  "${CHROMIUM_BIN}" \
    --headless \
    --disable-gpu \
    --run-all-compositor-stages-before-draw \
    --force-device-scale-factor=1 \
    --virtual-time-budget="${CHROMIUM_VIRTUAL_TIME_BUDGET}" \
    --user-data-dir="${tmp_profile}" \
    --no-first-run \
    --no-default-browser-check \
    --hide-scrollbars \
    --screenshot="${out_png}" \
    --window-size="${window_width},${window_height}" \
    "file://${tmp_html}" \
    >/dev/null 2>&1

  rm -f "${tmp_html}"
  rm -f "${tmp_svg}"
  rm -rf "${tmp_profile}"
}

render_png_from_svg_with_puppeteer() {
  local svg_file="$1"
  local out_png="$2"
  local svg_for_render
  local svg_dir
  local svg_name
  local svg_width
  local svg_height
  local window_width
  local window_height
  local tmp_html
  local tmp_svg
  local chromium_path

  if ! command -v node >/dev/null 2>&1; then
    return 2
  fi

  chromium_path="${CHROMIUM_BIN}"
  if [[ -n "${CHROMIUM_BIN}" && "${CHROMIUM_BIN}" != /* ]]; then
    chromium_path="$(command -v "${CHROMIUM_BIN}" 2>/dev/null || true)"
  fi
  if [[ -z "${chromium_path}" ]]; then
    return 2
  fi

  svg_dir="$(cd "$(dirname "${svg_file}")" && pwd)"
  svg_name="$(basename "${svg_file}")"

  tmp_svg="${svg_dir}/.__svgshot_render_$$.svg"
  prepare_svg_for_chromium "${svg_file}" "${tmp_svg}"
  svg_for_render="${tmp_svg}"
  svg_name="$(basename "${svg_for_render}")"

  svg_width="$(sed -n 's/.* width="\([0-9]\+\)px".*/\1/p' "${svg_file}" | head -n1)"
  svg_height="$(sed -n 's/.* height="\([0-9]\+\)px".*/\1/p' "${svg_file}" | head -n1)"

  if [[ -n "${svg_width}" && -n "${svg_height}" ]]; then
    window_width="$((svg_width + 2 * CHROMIUM_HTML_PADDING))"
    window_height="$((svg_height + 2 * CHROMIUM_HTML_PADDING))"
  else
    window_width="1700"
    window_height="1000"
  fi

  tmp_html="${svg_dir}/.__svgshot_tmp_$$.html"
  cat >"${tmp_html}" <<EOF
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    html, body {
      margin: 0;
      padding: ${CHROMIUM_HTML_PADDING}px;
      overflow: hidden;
      background: #fff;
      box-sizing: border-box;
      width: ${window_width}px;
      height: ${window_height}px;
    }
    img {
      display: block;
      width: ${svg_width}px;
      height: ${svg_height}px;
    }
  </style>
</head>
<body>
  <img id="diagram" src="${svg_name}" alt="diagram">
</body>
</html>
EOF

  mkdir -p "${PUPPETEER_CACHE_DIR}" >/dev/null 2>&1 || true

  # Ensure puppeteer-core is available without polluting the repo.
  if ! NODE_PATH="${PUPPETEER_CACHE_DIR}/node_modules" node -e "require.resolve('puppeteer-core')" >/dev/null 2>&1; then
    if [[ "${AUTO_INSTALL_PUPPETEER}" == "1" ]]; then
      npm --prefix "${PUPPETEER_CACHE_DIR}" init -y >/dev/null 2>&1 || true
      if ! npm --prefix "${PUPPETEER_CACHE_DIR}" install --silent "puppeteer-core@${PUPPETEER_VERSION}" >/dev/null 2>&1; then
        rm -f "${tmp_html}"
        return 1
      fi
    else
      rm -f "${tmp_html}"
      return 2
    fi
  fi

  if ! NODE_PATH="${PUPPETEER_CACHE_DIR}/node_modules" \
    __HTML_PATH="${tmp_html}" \
    __OUT_PNG="${out_png}" \
    __CHROMIUM_BIN="${chromium_path}" \
    __WINDOW_W="${window_width}" \
    __WINDOW_H="${window_height}" \
      node - <<'NODE'
const fs = require('fs');
const path = require('path');

const puppeteer = require('puppeteer-core');

const htmlPath = process.env.__HTML_PATH;
const outPng = process.env.__OUT_PNG;
const chromiumBin = process.env.__CHROMIUM_BIN;
const windowWidth = Number(process.env.__WINDOW_W);
const windowHeight = Number(process.env.__WINDOW_H);

(async () => {
  const browser = await puppeteer.launch({
    executablePath: chromiumBin,
    headless: 'new',
    args: [
      '--no-sandbox',
      '--disable-gpu',
      '--disable-dev-shm-usage',
      '--hide-scrollbars',
      '--force-device-scale-factor=1',
      '--disable-features=PaintHolding',
    ],
    defaultViewport: { width: windowWidth, height: windowHeight, deviceScaleFactor: 1 },
  });

  try {
    const page = await browser.newPage();
    await page.goto('file://' + htmlPath, { waitUntil: 'load' });

    // Wait for the SVG image to be loaded and decoded.
    await page.waitForFunction(() => {
      const img = document.getElementById('diagram');
      return img && img.complete && img.naturalWidth > 0;
    }, { timeout: 30000 });

    await page.evaluate(async () => {
      const img = document.getElementById('diagram');
      if (img && img.decode) {
        try { await img.decode(); } catch (_) {}
      }
      await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
    });

    await new Promise(r => setTimeout(r, 200));

    await page.screenshot({
      path: outPng,
      clip: { x: 0, y: 0, width: windowWidth, height: windowHeight },
      omitBackground: false,
    });
  } finally {
    await browser.close();
  }
})().catch(err => {
  console.error(err && err.stack ? err.stack : String(err));
  process.exit(1);
});
NODE
  then
    rm -f "${tmp_html}"
    rm -f "${tmp_svg}"
    return 1
  fi

  rm -f "${tmp_html}"
  rm -f "${tmp_svg}"
}

run_drawio() {
  # drawio-desktop (Electron) may emit noisy dbus/MESA/GLX warnings on Linux/WSL.
  # Filter only known-harmless lines while keeping all real errors.
  local stderr_file
  stderr_file="$(mktemp /tmp/drawio-stderr.XXXXXX)"

  if ! "${DRAWIO_BIN}" "$@" 2>"${stderr_file}"; then
    cat "${stderr_file}" >&2
    rm -f "${stderr_file}"
    return 1
  fi

  if [[ -s "${stderr_file}" ]]; then
    # Drop known noisy warnings.
    grep -Ev \
      'dbus/object_proxy\\.cc:573|StartTransientUnit: object_path= /org/freedesktop/systemd1|MESA: error: ZINK: failed to choose pdev|glx: failed to create drisw screen' \
      "${stderr_file}" \
      >&2 \
      || true
  fi

  rm -f "${stderr_file}"
}

export_one() {
  local in_file="$1"
  local out_png="$2"
  local out_svg="$3"
  local out_pdf
  local out_prefix

  if [[ ! -f "${in_file}" ]]; then
    echo "Error: input file not found: ${in_file}" >&2
    return 1
  fi

  # Add an explicit border around the cropped SVG bounds so right/bottom edges
  # don't get clipped due to text metrics differences across renderers.
  run_drawio --export --format svg --width 1600 --height 960 --border "${PNG_PADDING}" --output "${out_svg}" "${in_file}"
  if [[ ! -s "${out_svg}" ]]; then
    echo "Error: drawio did not produce SVG: ${out_svg}" >&2
    return 1
  fi
  out_pdf="${out_png%.png}.pdf"
  out_prefix="${out_png%.png}"

  case "${PNG_RENDERER}" in
    chromium)
      if [[ -n "${CHROMIUM_BIN}" ]]; then
        if [[ "${CHROMIUM_SHOTTER}" == "puppeteer" ]]; then
          if ! render_png_from_svg_with_puppeteer "${out_svg}" "${out_png}"; then
            render_png_from_svg_with_chromium "${out_svg}" "${out_png}"
          fi
        else
          render_png_from_svg_with_chromium "${out_svg}" "${out_png}"
        fi
      elif [[ -n "${PDFTOCAIRO_BIN}" ]]; then
        run_drawio --export --format pdf --border "${PNG_PADDING}" --output "${out_pdf}" "${in_file}"
        if [[ ! -s "${out_pdf}" ]]; then
          echo "Error: drawio did not produce PDF: ${out_pdf}" >&2
          return 1
        fi
        "${PDFTOCAIRO_BIN}" -png -singlefile -r "${PNG_DPI}" "${out_pdf}" "${out_prefix}"
        rm -f "${out_pdf}"
      else
        run_drawio --export --format png --width 1600 --height 960 --output "${out_png}" "${in_file}"
      fi
      ;;
    native)
      # Use drawio's own PNG export (closest to diagrams.net export semantics).
      run_drawio --export --format png --width 1600 --height 960 --output "${out_png}" "${in_file}"
      ;;
    pdf|*)
      if [[ -n "${PDFTOCAIRO_BIN}" ]]; then
        run_drawio --export --format pdf --border "${PNG_PADDING}" --output "${out_pdf}" "${in_file}"
        if [[ ! -s "${out_pdf}" ]]; then
          echo "Error: drawio did not produce PDF: ${out_pdf}" >&2
          return 1
        fi
        "${PDFTOCAIRO_BIN}" -png -singlefile -r "${PNG_DPI}" "${out_pdf}" "${out_prefix}"
        rm -f "${out_pdf}"
      elif [[ -n "${CHROMIUM_BIN}" ]]; then
        render_png_from_svg_with_chromium "${out_svg}" "${out_png}"
      else
        run_drawio --export --format png --width 1600 --height 960 --output "${out_png}" "${in_file}"
      fi
      ;;
  esac

  if [[ ! -s "${out_png}" ]]; then
    echo "Error: expected PNG not created: ${out_png}" >&2
    return 1
  fi
}

mkdir -p "${EXPORT_DIR}"

export_one "${SCRIPT_DIR}/figure_01-1.drawio" "${FIGURES_DIR}/figure_01-1.png" "${EXPORT_DIR}/figure_01-1.svg"
export_one "${SCRIPT_DIR}/figure_02.drawio" "${FIGURES_DIR}/figure_02.png" "${EXPORT_DIR}/figure_02.svg"
export_one "${SCRIPT_DIR}/figure_02-1.drawio" "${FIGURES_DIR}/figure_02-1.png" "${EXPORT_DIR}/figure_02-1.svg"

echo "Export complete."
