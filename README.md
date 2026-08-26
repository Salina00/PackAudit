# PackAudit

Automated compliance checker for packaged commodity labels, built for SIH26034 (Ministry of Consumer Affairs, Food & Public Distribution, Legal Metrology Division).

## Table of Contents

- [About](#about)
- [What it checks](#what-it-checks)
- [How it works](#how-it-works)
- [Tech stack](#tech-stack)
- [Getting started](#getting-started)
- [Project structure](#project-structure)
- [Known limitations](#known-limitations)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [Team](#team)
- [License](#license)

## About

Every pre-packaged product sold in India has to carry a fixed set of declarations under the Legal Metrology (Packaged Commodities) Rules, 2011. MRP, net quantity, manufacturing date, country of origin, and a handful of others. In practice, checking these manually across thousands of listings and retail products isn't something inspectors or platforms can keep up with.

PackAudit takes a photo of a label (or an e-commerce listing) and runs it through the actual rulebook, flagging exactly what's missing or non-compliant, instead of just guessing whether text is present.

## What it checks

We're not just looking for "is text present." We're validating against the specific rules that govern each declaration.

| # | Rule | What's validated |
|---|------|-------------------|
| 1 | Rule 6(1)(a) | Manufacturer / packer / importer name and address |
| 2 | Rule 6(1)(b) | Common or generic product name |
| 3 | Rule 6(1)(c) | Net quantity (weight, volume, or count) |
| 4 | Rule 6(1)(d) | Month and year of manufacture |
| 5 | Rule 6(1)(f) | MRP, inclusive of taxes declaration |
| 6 | Rule 6(1)(g) | Consumer care / complaint contact |
| 7 | Rule 18 | MRP not tampered or exceeded at sale |
| 8 | Rule 26 | Exemption handling (sub 10g/ml packs, drugs, institutional sale, etc.) |
| 9 | Rule 6(9) | Country of origin declaration |
| 10 | Rule 6(3) | Font height vs. package surface area (Second Schedule ratios) |
| 11 | Rule 8 | Declared quantity against standard prescribed pack sizes |
| 12 | Rule 23 | E-commerce listings mirror physical package declarations |

Checks 9 through 12 are the ones most tools in this space skip. Origin declaration, font size proportionality, and standard pack size validation all require actually parsing the rule text, not just running OCR and calling it done.

## How it works

```
Image / listing URL
      |
      v
Preprocessing (deskew, denoise, binarize)
      |
      v
OCR + text region detection (PaddleOCR)
      |
      v
Field extraction (regex + NER)
      |
      v
Rule engine (12 checks, with exemption logic)
      |
      v
Compliance report (pass/fail per field + suggested fix)
```

For Check 10 specifically, we calibrate pixel to mm measurements using a reference object in frame, then compare font height against the Principal Display Panel (PDP) area per the Second Schedule.

## Tech stack

- OCR: PaddleOCR
- Field extraction: spaCy (NER) plus regex patterns for structured fields like MRP and dates
- Rule engine: Python, rule definitions kept as a separate config file so they're easy to update if the law changes
- Measurement (Check 10): OpenCV for edge detection and pixel to mm calibration
- Backend: FastAPI
- Frontend: React
- Browser extension: for live checking on e-commerce listings (Chrome, Manifest V3)

## Getting started

Clone the repo and set up the backend and frontend separately.

```bash
git clone https://github.com/<your-org>/packaudit.git
cd packaudit
```

Backend:

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Add a `.env` file in `/backend` with:

```
OCR_ENGINE=paddleocr
DEBUG=True
```

## Project structure

```
packaudit/
    backend/
        ocr/              OCR pipeline and preprocessing
        extraction/       field parsing, NER models
        rules/            the 12 compliance checks and exemption logic
        measurement/      Check 10, font height / PDP ratio
        main.py
    frontend/              React dashboard
    extension/              Chrome extension for live e-commerce checks
    docs/
        rules-reference.md   plain language summary of each rule we check
```

## Known limitations

- OCR accuracy drops on curved packaging, glare, and heavily stylized fonts. We fall back to manual field correction rather than silently guessing.
- Check 10 needs a reference object in frame for calibration. Without one, the measurement is skipped and flagged as "unverifiable" rather than failed.
- Regional language labels (Hindi / state language declarations) are partially supported. English field detection is the most reliable right now.

## Roadmap

- [ ] Multi language label support
- [ ] Batch upload for inspector use (check 50+ listings at once)
- [ ] Heatmap dashboard showing non-compliance clusters by category/region
- [ ] Auto suggested fix text for each flagged field

## License

MIT
