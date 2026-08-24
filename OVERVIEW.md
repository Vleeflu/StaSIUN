# StaSIUN — Overview

## Purpose

A WebGIS decision-support platform that treats KAI (Kereta Api Indonesia) station commercial spaces as an auditable asset portfolio — answering not just "where is the asset" but "how much is it worth, who's the right user for it, and how can that value be optimized." The core problem it targets: KAI's non-farebox revenue sits at ~4% of total revenue vs. 30–40% for comparable operators like MRT Jakarta, because station commercial space is priced by guesswork rather than measurement.

## What Data Is Used

| Source | Content | Processing |
|---|---|---|
| **StrukGo** (MAPID) | Receipt photos → transaction value, payment method (cashless ratio as purchasing-power proxy) | OCR |
| **MenuGo** (MAPID) | Structured tenant + menu price data, buyer density, tenant mobility | Direct (no OCR needed) |
| **PropertiGo** (MAPID) | Property category/status; rental price benchmark from signage photos | OCR, with visual-tier fallback |
| **Activity** (MAPID) | Commuter review/complaint corpus | NLP corpus (LDA, NER, Sentiment) |
| **OpenStreetMap** | Pedestrian network, POI | Isochrone + density calc |
| **Station passenger volume** | Secondary data | Impressions basis |
| **MAPID APPS field surveys** | Curated validation surveys | Fills weak-coverage zones |

Unit of analysis: KRL/KCI stations in DKI Jakarta (initial scope), architecture designed to scale to Jabodetabek and other KAI/TOD areas.

## What's Been Built (planning artifact)

A build list (`StaSIUN_Build_List.md`) breaking the proposal's architecture into concrete build tasks across 8 layers: data layer (PostGIS), ingestion/OCR pipeline, AI/analytics layer (LDA/NER/Sentiment/OCR), scoring engine (SEPI/TSI/Naming Rights), presentation layer (Next.js/MapLibre), the three feature modules, the AI Insight panel, and non-functional targets — plus the 5-stage build order from Section V.1.

## Output Expectations

The system produces three outputs, one per feature:

| Feature | Output |
|---|---|
| **Ad-Space Opportunity** | Ranked brand categories per zone, rental value estimate, CSR-based Facility Sponsorship trigger |
| **Tenant Valuation** | Ranked tenant category for vacant lapak + Tenant Survival Index (0–100 score) |
| **Naming Rights** | Estimated annual contract value + ranked sponsor candidates |

All three are driven by a shared composite score, **SEPI** (Spatial Economic Potential Index — Transport, Economy, Accessibility, Urban, Commercial variables), computed via Entropy Weighting + AHP → TOPSIS ranking, presented as an interactive map (heatmaps, isochrone zones, indoor polygons) with an **AI Insight panel** for querying scores and running what-if scenarios (e.g., "what happens to TSI if I change the rent assumption").

Performance target: map load < 3s, spatial query < 500ms, near-zero infra cost via free-tier stack (Vercel, Supabase, MapLibre, OSM).