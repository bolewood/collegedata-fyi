# S2.7 Finance semantics (corrected)

## Storage rule (tools/ipeds/project.py:121)
`numeric < 0 && value_label exists → status fact`
`numeric < 0 && no label → numeric fact (preserved)`
No blanket allowNegative registry — would preserve sentinels -1/-2.

Evidence: `test_negative_finance_value_without_value_label_stays_numeric` preserves unlabeled -725000 as numeric.

## Draw rate (build_endowment_draw_rate_recipe.py)
- Residual F2H03D is preserved raw; denominator is F2H01 (not D). Builder excludes derived rate on `accounting_identity_mismatch` (exact Decimal equality, line 303) or `nonpositive_beginning_value` (288), does not null raw components.
- Formula: `abs(F2H03C) / F2H01`.
- Thresholds and exclusions reported per year; eligible==0 fails hard.

## Imputation
`X<var>` flag: quality_flag → imputed only when label contains "imput" (quality_from_label).

## Release identity
--display-groups scoped upsert; collection_year strict match; Access fallback for Finance F2 table availability.
