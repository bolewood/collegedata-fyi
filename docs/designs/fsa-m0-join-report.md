# FSA nonpayment M0 join report

Sanitized spike report for the May 2026 FSA institutional nonpayment workbook.
The xlsx stays in gitignored `scratch/fsa/`. This file is the M1 gate.

## Source

- Listing: https://studentaid.gov/data-center/student/portfolio (in-page search: `nonpayment`)
- File: `https://studentaid.gov/sites/default/files/fsawg/datacenter/library/nonpayment-rates.xlsx`
- SHA-256: `c541dd09d4dc6e62535b139f86ef72f9a51937fa3da3edad1a221c6d3efa921e`
- Title: Nonpayment Rates by Institution (as of May 2026)
- Public as-of: **late May 2026** (`as_of_date` 2026-05-31; delinquency pull date from Definitions, not the June 23 announcement)
- Cohort window: Direct Loan borrowers who entered repayment 2020-01-01 through 2025-05-31
- Older vintages: only the current hosted file is still at the stable Data Center URL

## Headers, grain, units

- School-level sheet header row: **3**
- Columns: `OPE ID`, `School Name`, `School Type`, `State`, `Total Borrowers Evaluated`, `Nonpayment Rate`
- FSA OPE ID grain: **6-digit** main-campus key (Definitions: "six-digit code identifying the school at its main branch")
- Excel storage: mostly **text** with `000000` format; numeric cells must still restore leading zeros without padding 6-digit keys to 8
- Rate scale: **0-1** (UI multiplies by 100)
- Suppression tokens: `<10%`, `<2%`, `<3%`, `<4%`, `<5%`, `Not Calculated`; denom token `<100`
- Small-n cut: n < 10 (file already rounds denom to nearest 100)

## Join counts (in-scope directory)

| Metric | Count |
| --- | --- |
| FSA school-level rows | 5719 |
| In-scope directory rows | 3000 |
| Exact 8-digit matches | 0 |
| 6-digit main rollups | 2500 |
| Unmatched FSA rows | 3219 |
| Directory in-scope with null Scorecard OPEID | 19 |
| `school_id`s with >1 matched FSA row before collapse | 0 |
| Omitted after collapse | 0 |
| Kept matched school_ids | 2500 |

Unmatched reasons: `{'main_opeid6': 2500, 'no_in_scope_main': 3219}`

## Scorecard vs IPEDS HD OPEID coverage (in-scope)

- Scorecard OPEID present: **2981** of 3000 in-scope
- HD2024 OPEID present: **2988** of 3000 in-scope
- HD-only (Scorecard null): 10 (6 mains, 4 branches)
- Scorecard-only (HD null): 3
- Missing both: 9
- HD beats Scorecard: **true**, by 7

M1 does **not** switch the annual directory writer to HD. Scorecard remains the native OPEID for `load_directory.py`. The surgical fill uses Scorecard first, then HD for remaining in-scope nulls (the 10 gaps). That keeps the 3 Scorecard-only keys and adds the 10 HD-only keys. Wholesale HD would drop Bethlehem College & Seminary, Northern Pennsylvania Regional College, and URBE University.

## Named rows

- University of Florida: FSA `001535` → `uf` (rollup_6) rate=0.05
- UEI College: FSA `031133` → `None` (unmatched) rate=0.56
- UEI College: FSA `039696` → `None` (unmatched) rate=0.54
- Miller-Motte: FSA `023068` → `miller-motte-college-chattanooga` (rollup_6) rate=0.5
- Miller-Motte: FSA `004992` → `None` (unmatched) rate=0.38
- Miller-Motte: FSA `026142` → `None` (unmatched) rate=0.35
- University of California-Berkeley: FSA `00131200` → `uc-berkeley` (directory) rate=n/a
- Pomona College: FSA `00117300` → `pomona-college` (directory) rate=n/a
