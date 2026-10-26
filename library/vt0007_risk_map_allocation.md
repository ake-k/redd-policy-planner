---
id: vt0007_risk_map_allocation
source: Verra VT0007 Unplanned Deforestation Allocation
standard: JNR
version: v1.0
section: "5.3.2.3 Quantity Adjustment; 5.5 Testing and Model Selection; 5.6 Using the Allocated Risk Map"
page: 25
---
Allocation means spatially dividing the jurisdictional unplanned deforestation baseline or FREL and assigning parts to projects and lower-level programs according to the risk inside each area; under JNR the allocated parts become their baselines (3.1, p.5).

How it works:
- Quantity adjustment (p.20): the prediction density map is scaled by AR = expected deforestation / modeled deforestation so that the map total equals the jurisdiction's activity-data estimate for the baseline validity period, iterated until no pixel exceeds its maximum density, then converted back to an annual rate.
- Model choice (5.5, pp.22-24): an alternative map is used only if its median absolute error beats the benchmark in both the fit test and the prediction test.
- Using the map (5.6.1, p.25): allocated risk is expected deforestation in ha/pixel/year; summing pixels inside a project area or leakage belt gives its projected deforestation.
- Emissions (5.6.2, p.25): multiply the risk map by a stratum emission-factor map (tCO2e/ha) and sum within the polygon.
- Negligible risk threshold: distance from forest edge containing 99.5% of historical deforestation (p.5).
