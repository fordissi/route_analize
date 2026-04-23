import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

function columnLetter(index) {
  let current = index;
  let result = "";
  while (current > 0) {
    const remainder = (current - 1) % 26;
    result = String.fromCharCode(65 + remainder) + result;
    current = Math.floor((current - 1) / 26);
  }
  return result;
}

function normalizeRows(rows) {
  const width = rows.reduce((max, row) => Math.max(max, Array.isArray(row) ? row.length : 0), 1);
  return rows.map((row) => {
    const source = Array.isArray(row) ? row : [];
    return [...source, ...Array(Math.max(width - source.length, 0)).fill("")];
  });
}

const inputPath = process.argv[2];
const outputPath = process.argv[3];

if (!inputPath || !outputPath) {
  throw new Error("Usage: node build_google_sheet_report.mjs <input-json> <output-xlsx>");
}

const payloadText = (await fs.readFile(inputPath, "utf8")).replace(/^\uFEFF/, "");
const payload = JSON.parse(payloadText);
const workbook = Workbook.create();
const sheetOrder = Array.isArray(payload.sheet_order) ? payload.sheet_order : Object.keys(payload.sheets || {});

for (const sheetName of sheetOrder) {
  const rows = normalizeRows(payload.sheets?.[sheetName] || [[""]]);
  const worksheet = workbook.worksheets.add(sheetName.slice(0, 31));
  const endCell = `${columnLetter(rows[0].length)}${rows.length}`;
  worksheet.getRange(`A1:${endCell}`).values = rows;
}

await fs.mkdir(path.dirname(outputPath), { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(outputPath);
