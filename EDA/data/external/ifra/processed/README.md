# IFRA Fragrance Ingredient Glossary

Source: IFRA Fragrance Ingredient Glossary, April 2020 Edition, The International Fragrance Association.

> Information derived from the IFRA Fragrance Ingredient Glossary, developed by The International Fragrance Association.

## Files

- Raw PDF: `data/external/ifra/raw/ifra-fragrance-ingredient-glossary-april-2020.pdf`
- Processed ingredients: `data/external/ifra/processed/ifra_ingredients_2020.csv`
- Primary descriptor definitions: `data/external/ifra/processed/ifra_primary_descriptor_definitions_2020.csv`
- Extraction date: 2026-09-01

## Columns

- `cas_number`: CAS number as printed; one row contains a parenthesized alternate CAS.
- `principal_name`: IFRA principal fragrance-ingredient name. A trailing PDF update marker (`*`) is removed.
- `primary_descriptor`: IFRA primary olfactory descriptor.
- `descriptor_2`, `descriptor_3`: additional co-occurring descriptors; their order is not interpreted as intensity.
- `source_page`: 1-based physical PDF page number.
- Definition data: `descriptor`, `definition`, `source_page`.

## Interpretation and use

This is fragrance-ingredient data, not a Fragrantica Note dictionary. A Fragrantica Note is a presentation concept and must not be assumed identical to an IFRA ingredient. Material-family and alias links in the analysis are candidates requiring manual review, not verified equivalence.

Before redistribution or public use, review the terms of use in the source PDF. The source states that use in whole or in part must credit The International Fragrance Association.
