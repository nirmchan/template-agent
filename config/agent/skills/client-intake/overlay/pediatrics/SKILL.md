---
name: client-intake
description: >
  Pediatrics overlay for client-intake. Narrows validation ranges for children
  aged 0-18 and requires age collection for growth chart context. Use when
  processing measurements for pediatric patients.
metadata:
  author: anonymous
  version: "1.0"
  overlay-source: pediatrics
compatibility: Requires base client-intake skill to be active.
---

# Client Intake - Pediatrics Override

This overlay adjusts the base client-intake skill for pediatric patients.

## Adjusted Validation Ranges

| Measurement | Base (Adult)  | Overlay (Pediatric) |
|-------------|---------------|---------------------|
| Height      | 50-272 cm     | 30-200 cm           |
| Weight      | 20-300 kg     | 2-150 kg            |

These replace the adult ranges from the base skill.

## Additional Required Field

Always collect patient age before processing measurements.

- For children under 2: ask age in months
- For children 2+: ask age in years
- If age is not provided, prompt: "What is the patient's age?"

## Output Format

Return measurements with age included:

```
- **Age:** <value> years (or months for infants)
- **Height:** <value> cm
- **Weight:** <value> kg
```

## Pediatrics-Specific Rules

- For infants under 2 years, measurement is recumbent length (lying down), not standing height
- Ask "Was this measured lying down or standing?" if age < 2 and not specified
- Flag any measurement below 1st or above 99th percentile for age as unusual
- Use WHO growth standards for children under 5, CDC charts for 5-18
