// Copies pdfjs-dist's worker file into public/ so it's served as a plain
// static asset instead of being bundled by webpack.
//
// Why this exists: components/pdf-page-viewer.tsx used to point
// pdfjsLib.GlobalWorkerOptions.workerSrc at the worker via
// `new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url)`. That
// works in `next dev`, but `next build` runs the emitted chunk through
// Terser, and the worker file is a real ES module (import/export) --
// Terser's default script parser can't handle that and the production
// build fails ("'import', and 'export' cannot be used outside of module
// code"). Routing the file through public/ means webpack never touches it.
//
// Runs automatically via the "postinstall" script in package.json, so the
// copied file always matches whatever pdfjs-dist version npm just
// installed (including on a fresh server deploy) -- it is deliberately not
// committed to git, same as the rest of node_modules-derived output.
const fs = require("fs");
const path = require("path");

const src = path.join(__dirname, "..", "node_modules", "pdfjs-dist", "build", "pdf.worker.min.mjs");
const destDir = path.join(__dirname, "..", "public");
const dest = path.join(destDir, "pdf.worker.min.mjs");

if (!fs.existsSync(src)) {
  console.error(`[copy-pdf-worker] Expected pdfjs-dist worker at ${src} but it wasn't found.`);
  console.error("[copy-pdf-worker] Is pdfjs-dist installed? Check the version pin in package.json.");
  process.exit(1);
}

fs.mkdirSync(destDir, { recursive: true });
fs.copyFileSync(src, dest);
console.log(`[copy-pdf-worker] Copied pdf.worker.min.mjs -> ${path.relative(process.cwd(), dest)}`);
