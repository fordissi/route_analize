import { chromium } from "playwright";
import { pathToFileURL } from "node:url";

const [, , htmlPath, pdfPath] = process.argv;

if (!htmlPath || !pdfPath) {
  console.error("Usage: node tools/html_to_pdf.mjs <input.html> <output.pdf>");
  process.exit(2);
}

let browser;
try {
  browser = await chromium.launch({ channel: "chrome", headless: true });
} catch {
  browser = await chromium.launch({ headless: true });
}
try {
  const page = await browser.newPage({ viewport: { width: 794, height: 1123 } });
  await page.goto(pathToFileURL(htmlPath).href, { waitUntil: "networkidle" });
  await page.pdf({
    path: pdfPath,
    format: "A4",
    printBackground: true,
    preferCSSPageSize: true,
  });
} finally {
  await browser.close();
}
