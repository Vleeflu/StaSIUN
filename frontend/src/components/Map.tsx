"use client";

import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

import { FALLBACK_COLOR, LINE_COLOR } from "@/lib/lines";
import { SEPI_RAMP_EXPRESSION } from "@/lib/sepi";
import type { FeatureCollection } from "geojson";

import type { StationCollection, StationFeature } from "@/types/station";

const STYLE_URL = `https://v2.basemap.mapid.io/styles/street-v2.0/style.json?key=${process.env.NEXT_PUBLIC_MAPID_KEY}`;

const JAKARTA_CENTER: [number, number] = [106.8271129, -6.1754398];
const INITIAL_ZOOM = 11;

const ICON_SIZE = 60;

// Warna peran, dijaga sama dengan token di globals.css. MapLibre menggambar di
// kanvas WebGL, jadi tidak bisa membaca custom property CSS — nilainya harus
// ditulis di sini, dan berubahnya wajib berbarengan.
const COLOR_SEPI_UNSCORED = "#c9c4c1";
const COLOR_SELECT = "#f2c101";
const COLOR_REACH = "#a4249e";

const EMPTY: StationCollection = { type: "FeatureCollection", features: [] };

const EMPTY_POLYGONS: FeatureCollection = { type: "FeatureCollection", features: [] };

export type FlyTarget = {
  lon: number;
  lat: number;
  minZoom: number;
  nonce: number;
};

type Props = {
  data: StationCollection | null;
  showLabels: boolean;
  showSepi: boolean;
  isochrones: FeatureCollection | null;
  selected: StationFeature | null;
  flyTo: FlyTarget | null;
  onSelect: (station: StationFeature) => void;
};

function createPieIcon(colors: string[]): ImageData {
  const canvas = document.createElement("canvas");

  canvas.width = ICON_SIZE;
  canvas.height = ICON_SIZE;

  const ctx = canvas.getContext("2d");

  if (!ctx) {
    throw new Error("Canvas 2D tidak tersedia");
  }

  const center = ICON_SIZE / 2;
  const radius = center - 4;
  const slice = (Math.PI * 2) / colors.length;

  colors.forEach((color, i) => {
    const start = -Math.PI / 2 + i * slice;

    ctx.beginPath();
    ctx.moveTo(center, center);
    ctx.arc(center, center, radius, start, start + slice);
    ctx.closePath();

    ctx.fillStyle = color;
    ctx.fill();
  });

  ctx.beginPath();
  ctx.arc(center, center, radius, 0, Math.PI * 2);
  ctx.lineWidth = 3;
  ctx.strokeStyle = "#ffffff";
  ctx.stroke();

  return ctx.getImageData(0, 0, ICON_SIZE, ICON_SIZE);
}

export default function Map({
  data,
  showLabels,
  showSepi,
  isochrones,
  selected,
  flyTo,
  onSelect,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);

  const dataRef = useRef<StationCollection | null>(data);
  const selectRef = useRef(onSelect);

  const [mapReady, setMapReady] = useState(false);

  useEffect(() => {
    dataRef.current = data;
    selectRef.current = onSelect;
  }, [data, onSelect]);

  useEffect(() => {
    const container = containerRef.current;

    if (!container) return;

    const map = new maplibregl.Map({
      container,
      style: STYLE_URL,
      center: JAKARTA_CENTER,
      zoom: INITIAL_ZOOM,
      attributionControl: false,
    });

    mapRef.current = map;

    map.addControl(new maplibregl.NavigationControl(), "bottom-left");

    map.addControl(
      new maplibregl.AttributionControl({ compact: true }),
      "bottom-left"
    );

    map.on("styleimagemissing", (e) => {
      if (map.hasImage(e.id)) return;

      map.addImage(e.id, {
        width: 1,
        height: 1,
        data: new Uint8Array(4),
      });
    });

    map.on("load", () => {
      setMapReady(true);
    });

    const observer = new ResizeObserver(() => map.resize());
    observer.observe(container);

    return () => {
      observer.disconnect();
      map.remove();
      mapRef.current = null;
      setMapReady(false);
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;

    if (!map || !mapReady || !data) return;

    for (const feature of data.features) {
      const key = feature.properties.line_key || "none";

      if (map.hasImage(key)) continue;

      const colors =
        key === "none"
          ? [FALLBACK_COLOR]
          : key.split("-").map((name) => LINE_COLOR[name] ?? FALLBACK_COLOR);

      map.addImage(key, createPieIcon(colors), { pixelRatio: 2 });
    }

    const source = map.getSource("stations");

    if (source) {
      (source as maplibregl.GeoJSONSource).setData(data);
      return;
    }

    map.addSource("stations", { type: "geojson", data });
    map.addSource("selected-station", { type: "geojson", data: EMPTY });
    map.addSource("isochrones", { type: "geojson", data: EMPTY_POLYGONS });

    map.addLayer({
      id: "isochrone-fill",
      type: "fill",
      source: "isochrones",
      layout: { visibility: "none" },
      paint: {
        "fill-color": COLOR_REACH,
        "fill-opacity": [
          "match",
          ["get", "minutes"],
          5,
          0.18,
          10,
          0.12,
          0.07,
        ],
      },
    });

    map.addLayer({
      id: "isochrone-line",
      type: "line",
      source: "isochrones",
      layout: { visibility: "none" },
      paint: {
        "line-color": COLOR_REACH,
        "line-width": 1.2,
        "line-opacity": 0.55,
      },
    });

    map.addLayer({
      id: "selected-ring",
      type: "circle",
      source: "selected-station",
      paint: {
        "circle-radius": [
          "interpolate",
          ["linear"],
          ["zoom"],
          10,
          18,
          14,
          28,
          18,
          42,
        ],
        "circle-color": COLOR_SELECT,
        "circle-opacity": 0.16,
        "circle-stroke-width": 2.5,
        "circle-stroke-color": COLOR_SELECT,
      },
    });

    map.addLayer({
      id: "stations-sepi",
      type: "circle",
      source: "stations",
      layout: { visibility: "none" },
      paint: {
        "circle-radius": [
          "interpolate",
          ["linear"],
          ["zoom"],
          10,
          12,
          14,
          21,
          18,
          32,
        ],
        "circle-color": [
          "case",
          ["==", ["get", "sepi"], null],
          COLOR_SEPI_UNSCORED,
          ["interpolate", ["linear"], ["get", "sepi"], ...SEPI_RAMP_EXPRESSION],
        ],
        "circle-opacity": 0.75,
        "circle-stroke-width": 1,
        "circle-stroke-color": "#ffffff",
      },
    });

    map.addLayer({
      id: "stations-circle",
      type: "symbol",
      source: "stations",
      layout: {
        "icon-image": ["coalesce", ["get", "line_key"], "none"],
        "icon-size": ["interpolate", ["linear"], ["zoom"], 10, 0.45, 14, 0.8, 18, 1.25],
        "icon-allow-overlap": true,
      },
      paint: {
        "icon-opacity": ["case", ["get", "served"], 1, 0.4],
      },
    });

    map.addLayer({
      id: "stations-label",
      type: "symbol",
      source: "stations",
      layout: {
        "text-field": ["get", "name"],
        "text-font": ["Noto Sans Regular"],
        "text-size": 11,
        "text-offset": [0, 1.6],
        "text-anchor": "top",
        visibility: "none",
      },
      paint: {
        "text-color": "#201e1d",
        "text-halo-color": "#ffffff",
        "text-halo-width": 1.5,
      },
    });

    const handleClick = (e: maplibregl.MapLayerMouseEvent) => {
      const hit = e.features?.[0];
      const collection = dataRef.current;

      if (!hit || !collection) return;

      const match = collection.features.find((f) => f.id === hit.id);

      if (match) selectRef.current(match);
    };

    for (const layer of ["stations-circle", "stations-sepi"]) {
      map.on("click", layer, handleClick);
      map.on("mouseenter", layer, () => {
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", layer, () => {
        map.getCanvas().style.cursor = "";
      });
    }
  }, [mapReady, data]);

  useEffect(() => {
    const map = mapRef.current;

    if (!map || !mapReady || !map.getLayer("stations-label")) return;

    map.setLayoutProperty(
      "stations-label",
      "visibility",
      showLabels ? "visible" : "none"
    );
  }, [mapReady, showLabels]);

  useEffect(() => {
    const map = mapRef.current;

    if (!map || !mapReady || !map.getLayer("stations-sepi")) return;

    map.setLayoutProperty(
      "stations-sepi",
      "visibility",
      showSepi ? "visible" : "none"
    );
  }, [mapReady, showSepi]);

  useEffect(() => {
    const map = mapRef.current;
    const source = map?.getSource("isochrones");

    if (!map || !mapReady || !source || !map.getLayer("isochrone-fill")) return;

    (source as maplibregl.GeoJSONSource).setData(isochrones ?? EMPTY_POLYGONS);

    const visibility = isochrones ? "visible" : "none";
    map.setLayoutProperty("isochrone-fill", "visibility", visibility);
    map.setLayoutProperty("isochrone-line", "visibility", visibility);
  }, [mapReady, isochrones]);

  useEffect(() => {
    const map = mapRef.current;
    const source = map?.getSource("selected-station");

    if (!source) return;

    (source as maplibregl.GeoJSONSource).setData(
      selected ? { type: "FeatureCollection", features: [selected] } : EMPTY
    );
  }, [mapReady, selected]);

  useEffect(() => {
    const map = mapRef.current;

    if (!map || !flyTo) return;

    map.flyTo({
      center: [flyTo.lon, flyTo.lat],
      zoom: Math.max(map.getZoom(), flyTo.minZoom),
      duration: 1200,
    });
  }, [flyTo]);

  return <div ref={containerRef} className="h-full w-full" />;
}
