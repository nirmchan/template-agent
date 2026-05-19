---
name: bmi-report
description: >
  Pediatrics overlay for bmi-report. Replaces adult BMI categories with
  age-appropriate percentile-based assessment for children aged 2-18.
  Use when generating a BMI report for a pediatric patient.
metadata:
  author: anonymous
  version: "1.0"
  overlay-source: pediatrics
compatibility: Requires base bmi-report skill to be active.
---

# BMI Report - Pediatrics Override

For children aged 2-18, BMI interpretation uses age-and-sex percentile charts, not fixed adult categories.

## Pediatric BMI Categories (Percentile-Based)

| Percentile Range | Category       |
|-----------------|----------------|
| < 5th           | Underweight    |
| 5th - 84th      | Healthy weight |
| 85th - 94th     | Overweight     |
| >= 95th         | Obese          |

These replace the adult BMI ranges (18.5, 25, 30 cutoffs) from the base skill.

## Adjusted Workflow

1. Calculate BMI normally using height (cm) and weight (kg)
2. Do NOT apply adult categories to the result
3. Note that pediatric BMI requires percentile lookup by age and sex
4. Report the raw BMI value with pediatric context

## Output Format

```
## BMI Analysis (Pediatric)

- **Age:** [age]
- **Height:** [height] cm
- **Weight:** [weight] kg
- **BMI:** [calculated value]

### Interpretation

For a [age]-year-old [boy/girl], this BMI value needs to be plotted on
CDC/WHO growth charts to determine the percentile. Standard adult BMI
categories do not apply to children.

**Approximate guidance:**
- This BMI appears [below/within/above] the typical range for this age group.

### Disclaimer

This is not medical advice. Pediatric BMI interpretation requires clinical
growth charts and should be confirmed by a pediatrician.
```

## Key Differences from Adult Reports

- Never use adult category labels (Normal, Overweight, etc.) for children
- Always mention that percentile charts are needed for accurate classification
- Always recommend pediatrician confirmation
- Health tips should focus on active play and balanced nutrition, not weight management
- Tone: supportive, growth-focused, never alarming
