import fs from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { chromium } = require("C:/Users/Aarya/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright");

const output = fileURLToPath(new URL("./qa-workdna.png", import.meta.url));
const browser = await chromium.launch({ headless: true, executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe" });
const page = await browser.newPage({ viewport: { width: 1536, height: 1024 } });
const errors = [];
async function waitForRows() { await page.waitForTimeout(300); await page.waitForFunction(() => document.querySelectorAll("tbody tr").length > 1); }
page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
page.on("pageerror", (error) => errors.push(error.message));

await page.goto("http://127.0.0.1:8765", { waitUntil: "networkidle" });
await page.evaluate(() => localStorage.removeItem("workdna-assessments"));
await page.reload({ waitUntil: "networkidle" });
await page.getByRole("heading", { name: "WorkDNA ranking" }).first().waitFor();
await waitForRows();
const workdnaFirst = await page.locator("tbody tr").first().innerText();

await page.getByRole("button", { name: "Skill Evidence" }).click();
await page.getByRole("heading", { name: "Skill Evidence Ratio" }).first().waitFor();
await waitForRows();
const skillFirst = await page.locator("tbody tr").first().innerText();

await page.getByRole("button", { name: "Career Physics" }).click();
await page.getByText("Complexity over career").waitFor();
await waitForRows();
const physicsFirst = await page.locator("tbody tr").first().innerText();

await page.getByRole("button", { name: "Interview" }).click();
await page.getByRole("heading", { name: "Interview Calibration" }).first().waitFor();
await waitForRows();
const firstAssessment = page.locator(".assessment-grid select").first();
await firstAssessment.selectOption("4");
const interviewEvidence = await page.locator(".interview-score > div:nth-child(2) strong").innerText();
if (interviewEvidence !== "80.0") throw new Error(`Unexpected interview score: ${interviewEvidence}`);
await page.reload({ waitUntil: "networkidle" });
await page.getByRole("button", { name: "Interview" }).click();
await page.getByRole("heading", { name: "Interview Calibration" }).first().waitFor();
await waitForRows();
const persistedAssessment = await page.locator(".assessment-grid select").first().inputValue();
await page.screenshot({ path: output, fullPage: true });

const result = {
  url: page.url(),
  title: await page.title(),
  rankedRows: await page.locator("tbody tr").count(),
  distinctModelLeaders: new Set([workdnaFirst, skillFirst, physicsFirst]).size,
  interviewPersisted: persistedAssessment === "4",
  importVisible: await page.getByRole("button", { name: /Import dataset/i }).count(),
  exportVisible: await page.getByRole("button", { name: /Export current ranking/i }).count(),
  errors,
  screenshot: output,
};
await browser.close();
await fs.writeFile(new URL("./qa-browser-result.json", import.meta.url), JSON.stringify(result, null, 2));
console.log(JSON.stringify(result, null, 2));