---
id: jnr_s2_uncertainty
source: Verra JNR Scenario 2 Requirements
standard: JNR
version: v4.1
section: "3.15 Uncertainty"
page: 41
---
Programs analyze uncertainty qualitatively (systematic error) and quantitatively (random error), reported as the half-width of the two-sided 90% confidence interval as a percent of the mean (3.15.1-3.15.4, p.40). Leakage uncertainty need not be included (3.15.8, p.41).

Discounting (3.15.10-3.15.12, pp.41-43):
- Emission reduction estimates are discounted using Monte Carlo results and the Table 1 discount factors (p.42).
- Uncertainty of 10% or less -> no discount. Between 10% and 100%, the factor is uncertainty / 1.6449 x 0.4307 (e.g., about 8.51% for 30-35% uncertainty; ranges run up to about 25.5% for 95-100%).
- Uncertainty of 100% or more is not eligible for crediting (3.15.11, p.42).
- Discount = factor x estimated reductions; e.g., 100,000 t with 31% uncertainty -> 8,510 t (p.43).
- At the end of the reference level validity period, nested activities may recompute aggregate uncertainty and adjust creditable reductions (3.15.16, p.44).
