# Arts Council of Ireland Funding Decisions, 2022–2027

This repository contains a curated dataset of funding decisions published by the **Arts Council of Ireland / An Chomhairle Ealaíon** for four major funding programmes between **2022 and 2027**, together with the Python code used to harvest and clean the data.

The committed dataset contains **2,651 individual awards** with a combined nominal value of **€365,717,486**.

> **2027 is incomplete.** The dataset reflects decisions publicly available when the data were harvested in September 2026. At that point, 2027 Arts Grant Funding decisions were available, while the other 2027 programmes in scope had not yet produced published decisions.

## Project context

This dataset and the accompanying harvesting code were produced as part of **Minimal Curation: Minimal Computing for Sustainable Digital Sociocultural Heritage**, a project funded by **Research Ireland**. Minimal Curation investigates sustainable, accessible, and equitable approaches to digital sociocultural heritage, including the conditions under which arts and cultural organisations develop, preserve, and share digital cultural materials.

The dataset supports that work by providing a structured longitudinal view of selected Arts Council funding to organisations in Ireland.

## Repository contents

```text
.
├── README.md
├── arts-council-harvest.py
└── arts-council-funding-2022-2027.csv
```

- **`arts-council-funding-2022-2027.csv`** — the cleaned research dataset.
- **`arts-council-harvest.py`** — the harvesting and cleaning script used to reproduce the dataset from the Arts Council Funding Decisions website.

Running `arts-council-harvest.py` also creates `arts-council-funding-2022-2027-audit.json`, which records page-level extraction information, validation checks, and the known 2026 Arts Grant Funding discrepancy. Audit information is kept outside the research CSV so that the dataset remains a simple six-column file.

## Data source

The underlying data come from the Arts Council's public **Funding Decisions** database:

https://artscouncil.ie/funding/funding-decisions/

The website publishes award-level information including recipient, funding programme or round, location, artform, and amount awarded.

This repository is an independently compiled research dataset. It is not an official Arts Council publication.

## Scope

The dataset is restricted to four funding programmes that focus on organisations as opposed to individuals. This provides a consistent basis for examining patterns of institutional and organisational arts funding over time:

- **Arts Centre Partnership Funding**
- **Arts Grant Funding**
- **Strategic Funding**
- **Festivals Investment Scheme**

It covers funding decision years **2022–2027**.

### Programme-name normalisation

The Arts Council's naming has changed over time. To support longitudinal comparison, `arts-council-harvest.py` maps historical **Arts Centre Funding** / **Arts Centres Funding** records to:

```text
Arts Centre Partnership Funding
```

For the **Festivals Investment Scheme**, separately published rounds are intentionally collapsed to:

```text
Festivals Investment Scheme
```

Round numbers are therefore not represented in the final dataset.

## Dataset schema

`arts-council-funding-2022-2027.csv` contains one row per funding award and exactly six columns:

| Column | Description |
| --- | --- |
| `year` | Funding decision year |
| `fund` | Normalised funding programme |
| `recipient` | Funded organisation or individual as published by the Arts Council |
| `location` | Location classification published in the Arts Council database |
| `artform` | Artform/category, with the limited normalisations documented below |
| `amount_awarded` | Amount awarded in euro |

`amount_awarded` contains nominal euro values. No inflation adjustment has been made.

Locations have not been geocoded or independently standardised.

## Dataset summary

The committed CSV contains **2,651 awards**.

| Year | Awards | Total awarded |
| ---: | ---: | ---: |
| 2022 | 464 | €63,007,766 |
| 2023 | 473 | €66,649,379 |
| 2024 | 476 | €66,561,123 |
| 2025 | 494 | €74,158,503 |
| 2026 | 524 | €78,079,125 |
| 2027* | 220 | €17,261,590 |
| **Total** | **2,651** | **€365,717,486** |

\* 2027 is incomplete.

By programme:

| Fund | Awards | Total awarded |
| --- | ---: | ---: |
| Arts Centre Partnership Funding | 199 | €43,055,225 |
| Arts Grant Funding | 1,170 | €90,468,710 |
| Strategic Funding | 521 | €220,162,544 |
| Festivals Investment Scheme | 761 | €12,031,007 |

## How the code works

The full harvesting and cleaning workflow is implemented in **`arts-council-harvest.py`**.

The Arts Council Funding Decisions interface is dynamically generated and paginated. Ordinary HTTP requests do not reliably expose the complete award list, so the script uses **Playwright** with Chromium to work with the rendered public website.

For each year from 2022 through 2027, the script:

1. opens the year-filtered Funding Decisions page;
2. waits for the site's FacetWP results to render;
3. traverses every available results page;
4. parses recipient, raw round name, location, artform, and amount awarded;
5. combines and deduplicates the harvested records;
6. keeps records belonging to the four programmes in scope;
7. applies the exclusions and normalisations documented below;
8. writes the final six-column CSV; and
9. writes a separate audit JSON containing extraction and validation information.

The year-specific URLs take the form:

```text
https://artscouncil.ie/funding/funding-decisions/?_funding_decision_year=2026
```

The parser identifies the field labels used by the rendered funding records:

```text
Round Name
Location
Artform
Amount Awarded
```

Because this is a web scraper rather than an official API client, changes to the Arts Council site's HTML, pagination, or FacetWP configuration may require corresponding changes to `arts-council-harvest.py`.

## Cleaning decisions implemented in the code

The transformations below are explicitly encoded in `arts-council-harvest.py`, so the final CSV can be regenerated from the repository code rather than relying on undocumented manual edits.

### Excluded ancillary rounds

Several purpose-specific rounds contain the names of the core programmes but are not treated as part of those programmes in this dataset.

The script excludes:

- 2022 Arts Centre Funding – Touring
- 2023 Arts Centre Funding – Touring
- 2022 Strategic Funding – Touring
- 2023 Strategic Funding – Touring
- 2024 Strategic Funding – Access
- 2024 Strategic Funding – Touring

These exclusions remove **90 awards worth €3,183,254** from the broader initial harvest.

### Festivals Investment Scheme rounds

All Festivals Investment Scheme rounds are retained, but their round distinctions are collapsed into the single value:

```text
Festivals Investment Scheme
```

### Artform normalisation

A small number of source-label inconsistencies are normalised by the script:

| Source label | Dataset label |
| --- | --- |
| `Litearture (English Language)` | `Literature (English language)` |
| `Multidisciplinary arts` | `Multidisciplinary Arts` |
| `Trad Arts` | `Traditional Arts` |
| `Arts Participation` | `Participatory Arts` |

No wider attempt is made to redesign or merge the Arts Council's artform taxonomy.

## Validation

`arts-council-harvest.py` performs structural checks after cleaning and records them in the audit JSON.

The committed dataset contains:

- **2,651 rows**
- **0 duplicate rows**
- **0 missing values** across the six dataset fields
- **0 non-positive award amounts**

The script also reports award counts and totals for every year/programme combination so a fresh harvest can be compared with the committed dataset.

### Known Arts Grant Funding 2026 discrepancy

One source-level discrepancy remains intentionally unresolved.

The live Funding Decisions database yielded:

```text
213 awards
€16,739,531
```

for **Arts Grant Funding 2026** during the September 2026 harvest.

An Arts Council announcement published on 1 August 2025 described Arts Grant Funding 2026 as comprising **218 recipients** and approximately **€17.1 million**.

The repository does **not** reconstruct or fabricate five missing records. The CSV reflects the award records available through the live Funding Decisions database at the time of harvesting. The script records this issue in its audit JSON.

Researchers analysing the 2026 Arts Grant Funding subset should therefore account for this discrepancy.

## 2027 data

2027 should be treated as a **partial year**, not as a completed annual funding total.

At the time of harvesting, the dataset contained:

```text
Arts Grant Funding: 220 awards
Arts Centre Partnership Funding: not yet available
Strategic Funding: not yet available
Festivals Investment Scheme: not yet available
```

The absence of rows for the latter three programmes does not mean that their 2027 funding was zero.

A future re-run of `arts-council-harvest.py` may therefore produce additional 2027 records.

## Reproducing the dataset

### macOS

Using a virtual environment is recommended, particularly with Homebrew-managed Python.

From the repository directory:

```bash
python3 -m venv arts-env
source arts-env/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install playwright
python3 -m playwright install chromium
```

Run the scraper:

```bash
python3 arts-council-harvest.py
```

By default this writes:

```text
arts-council-funding-2022-2027.csv
arts-council-funding-2022-2027-audit.json
```

The CSV is the research dataset. The JSON is a reproducibility and validation record and does not form part of the tabular dataset.

To watch the browser while the scraper runs:

```bash
python3 arts-council-harvest.py --headful
```

To specify another output path:

```bash
python3 arts-council-harvest.py --output data/my-harvest.csv
```

When finished with the virtual environment:

```bash
deactivate
```

### Linux and Windows

The same Python/Playwright workflow applies, although virtual-environment activation commands differ by operating system.

## Reproducibility and versioning

The committed CSV should be treated as a **versioned research object**, rather than assuming that the live website will always reproduce it exactly.

The Arts Council's public database can change over time because of:

- newly published decisions;
- retrospective corrections;
- amended or withdrawn awards;
- changes to recipient metadata;
- changes to artform classifications; or
- changes to the website itself.

A later execution of `arts-council-harvest.py` may therefore differ from the CSV currently committed to the repository, particularly for 2027.

For reproducible research, cite the repository version, release, DOI, or Git commit corresponding to the CSV actually analysed.

## Suggested citation

If using the dataset in research, cite the repository and the version used. For example:

> O'Sullivan, James. *Arts Council of Ireland Funding Decisions, 2022–2027*. Dataset and harvesting code, 2026.

The underlying funding decisions should also be attributed to the **Arts Council of Ireland / An Chomhairle Ealaíon**.

## Data provenance

All underlying award information originates from the Arts Council's publicly accessible Funding Decisions database.

This repository:

- selects a defined subset of the published funding records;
- restructures them into a machine-readable CSV;
- normalises programme names for longitudinal comparison;
- excludes six documented Touring/Access rounds;
- normalises four documented artform-label inconsistencies; and
- provides the harvesting/cleaning code required to reproduce those decisions.

The repository does not independently verify the factual accuracy of individual Arts Council funding decisions.

## Licence

A software licence such as MIT can be applied to `arts-council-harvest.py`.

The licence attached to this repository's code does not automatically assign the same licence to the underlying Arts Council source data. Users should consult the Arts Council's terms and policies when reusing the original material.

If desired, the dataset and code can be assigned separate licence notices.

## Acknowledgements

Underlying funding data: **Arts Council of Ireland / An Chomhairle Ealaíon**.

Dataset compilation, cleaning, normalisation, and harvesting code: **James O'Sullivan**.

Produced as part of **Minimal Curation: Minimal Computing for Sustainable Digital Sociocultural Heritage**, funded by **Research Ireland** (COALESCE/2025/7121).
