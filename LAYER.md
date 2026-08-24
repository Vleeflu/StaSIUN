# StaSIUN — What Needs to Be Built

Derived from *Proposal WebGIS MAPID: StaSIUN* (Station Spatial Intelligence for Urban Network), Section III (Solusi yang Diusulkan) and Section V (Kelayakan Teknis).

## 1. Data Layer — PostgreSQL + PostGIS (Supabase)

- Schema design with dual projection: EPSG:4326 (rendering) + EPSG:32748 / UTM 48S (metric calculations)
- GiST spatial indexes on all geometry columns for fast `ST_DWithin` queries against hundreds of thousands of POIs
- pgRouting setup for isochrone generation (5/10/15-min walking zones, network-based, not circular buffers)
- Materialized views for precomputed scores, refreshed only on data change
- Ingestion tables for the four MAPID sources — StrukGo, MenuGo, PropertiGo, Activity — plus OSM POI/road network and station passenger volume

## 2. Data Ingestion & Preprocessing Pipeline

- OCR/vision extraction module — reads transaction values off StrukGo receipt photos and rental price benchmarks off PropertiGo signage photos, with fallback to qualitative visual tiering (premium/mid/economy) when OCR fails
- Data cleaning jobs: coordinate validation, duplicate point removal, merchant category normalization
- Spatial join pipeline: attach every point to its nearest station isochrone zone via network-based join
- Survey data intake from MAPID APPS field surveys (used to validate footfall persona assumptions at hub vs. mid-tier station archetypes)

## 3. Analytics / AI Layer (Python — GeoPandas, scikit-learn)

Four models, each capped at 15% contribution to final scores, gated by spatial cross-validation:

| Model | Build task |
|---|---|
| OCR/Vision | Receipt + signage number extraction, missing-value fallback logic |
| LDA (topic modeling) | Cluster Activity corpus into station archetypes (Hub Interchange, CBD Flagship, Commuter Residential, etc.) |
| NER | Detect organic brand mentions near stations → "brand geo-resonance" score |
| Sentiment Analysis | Indonesian-language polarity scoring on commuter complaints → facility-risk penalty / sponsorship trigger |

## 4. Scoring Engine

- **SEPI (Spatial Economic Potential Index):** $SEPI = w_1T + w_2E + w_3A + w_4U + w_5C$
  - Entropy Weighting module + AHP module (CR < 0.10 consistency check)
  - Combined weighting: $w = \lambda w_{entropy} + (1-\lambda)w_{AHP}$
  - TOPSIS ranking on top of combined weights
- **Tenant Survival Index (TSI)** — separate scoring formula (confirm exact derivation with the team, past proposal line ~400)
- **Naming Rights valuation model** — exposure + economic activity + brand geo-resonance → contract value estimate + sponsor candidate ranking
- Isochrone-based aggregation logic: transaction/POI density recalculated within isochrone boundaries instead of circular buffers

## 5. Presentation Layer (Next.js + MapLibre GL JS)

- Map rendering core with MAPID MAPS basemap, vector tiles via `ST_AsMVT`
- Layer overlays: SEPI heatmap, isochrone polygons, indoor station polygons (micro-scale lapak/ad-spot interactivity)
- Standard map interactions: zoom, click-for-attributes, filtering, location table, layer control toggle
- Responsive layout (desktop + mobile)
- Deployment config for Vercel/Netlify

## 6. Three Feature Modules (User-Facing)

1. **Ad-Space Opportunity** — brand category ranking per zone, rental value estimate, CSR-based Facility Sponsorship trigger UI
2. **Tenant Valuation (Matchmaking + TSI)** — vacant-lapak category ranking, 0–100 survival score display
3. **Naming Rights** — annual contract value estimate, sponsor candidate ranking with context

## 7. AI Insight Panel

- Query interface connecting SEPI/TSI/valuation scores with NLP findings, per zone/station
- What-if scenario simulator — e.g., adjust rent assumption → see TSI impact live (needs its own lightweight recompute path since it's user-triggered, unlike the precomputed batch scores)

## 8. Non-Functional Targets

- Map load < 3s, spatial query response < 500ms
- Zero-cost prototype stack (all components have free tiers: Vercel, Supabase, MapLibre, OSM)

---

## Build Order (per Section V.1 — 5-stage implementation plan)

1. Load & clean spatial data
2. OCR pipeline (StrukGo, PropertiGo)
3. Isochrone spatial join
4. SEPI/TSI/Naming Rights scoring (Entropy + AHP → TOPSIS)
5. Interactive map + AI Insight panel

*Relevant for the "Kelayakan Teknis" section (Marco + Cedrick).*