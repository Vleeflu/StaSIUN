"use client";

import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

import { FALLBACK_COLOR, LINE_COLOR } from "@/lib/lines";
import { SUPPLY_CATEGORIES, poiLabel } from "@/lib/poi";
import { REACH_BANDS } from "@/lib/reach";
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
const COLOR_POI = "#55504d";
// Keluhan fasilitas (F6-2). Warna ke-lima di peta, dan itu batasnya - dipakai
// hanya saat layernya dinyalakan pengguna, tidak pernah bersamaan dengan
// titik minat.
const COLOR_CSR = "#1f6f5c";

// Diurai satu per satu, bukan di-spread: tipe ekspresi MapLibre menuntut
// jumlah unsurnya pasti, dan spread menghilangkan informasi itu. Nilainya
// tetap dari lib/reach supaya tidak pernah beda dengan legenda.
const [BAND_NEAR, BAND_MID, BAND_FAR] = REACH_BANDS;

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
  /** Menit yang poligonnya digambar; sisanya disaring keluar. */
  reachMinutes: number[];
  pois: FeatureCollection | null;
  /** Penanda keluhan fasilitas yang lolos validasi spasial (F6-2). */
  sponsorship: FeatureCollection | null;
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
  reachMinutes,
  pois,
  sponsorship,
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
    map.addSource("station-pois", { type: "geojson", data: EMPTY_POLYGONS });
    map.addSource("sponsorship", { type: "geojson", data: EMPTY_POLYGONS });

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
          BAND_NEAR.minutes,
          BAND_NEAR.opacity,
          BAND_MID.minutes,
          BAND_MID.opacity,
          BAND_FAR.opacity,
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

    // Gerai komersial berisi penuh (pesaing), sisanya berongga (calon
    // pelanggan). Dibedakan lewat isian, bukan rona baru: peta sudah memikul
    // tiga peran warna plus enam warna line.
    map.addLayer({
      id: "poi-demand",
      type: "circle",
      source: "station-pois",
      filter: ["!", ["in", ["get", "category"], ["literal", [...SUPPLY_CATEGORIES]]]],
      layout: { visibility: "none" },
      paint: {
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 12, 2, 18, 5],
        "circle-color": "#ffffff",
        "circle-stroke-width": 1.2,
        "circle-stroke-color": COLOR_POI,
        "circle-opacity": 0.9,
      },
    });

    map.addLayer({
      id: "poi-supply",
      type: "circle",
      source: "station-pois",
      filter: ["in", ["get", "category"], ["literal", [...SUPPLY_CATEGORIES]]],
      layout: { visibility: "none" },
      paint: {
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 12, 2.5, 18, 5.5],
        "circle-color": COLOR_POI,
        "circle-stroke-width": 1,
        "circle-stroke-color": "#ffffff",
      },
    });

    // Keluhan yang statusnya 'tervalidasi' digambar padat; yang berdiri di atas
    // pengamatan surveyor digambar berongga. Bedanya harus terlihat di peta,
    // bukan cuma tertulis di panel.
    map.addLayer({
      id: "sponsorship-titik",
      type: "circle",
      source: "sponsorship",
      layout: { visibility: "none" },
      paint: {
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 11, 4, 16, 8],
        "circle-color": [
          "case",
          ["==", ["get", "status"], "tervalidasi"],
          COLOR_CSR,
          "#ffffff",
        ],
        "circle-stroke-width": 2,
        "circle-stroke-color": COLOR_CSR,
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

    const popup = new maplibregl.Popup({
      closeButton: false,
      offset: 10,
      className: "poi-popup",
    });

    for (const layer of ["poi-demand", "poi-supply"]) {
      map.on("mouseenter", layer, (e) => {
        const hit = e.features?.[0];
        if (!hit) return;

        map.getCanvas().style.cursor = "pointer";

        // Nama datang dari basis data, jadi ditempel lewat textContent —
        // tidak pernah lewat innerHTML, sekalipun kelihatannya aman.
        const box = document.createElement("div");
        const title = document.createElement("strong");
        title.textContent = String(hit.properties?.name ?? "");
        const kind = document.createElement("span");
        kind.textContent = poiLabel(String(hit.properties?.category ?? ""));

        box.append(title, document.createElement("br"), kind);
        popup.setLngLat(e.lngLat).setDOMContent(box).addTo(map);
      });

      map.on("mouseleave", layer, () => {
        map.getCanvas().style.cursor = "";
        popup.remove();
      });
    }

    map.on("mouseenter", "sponsorship-titik", (e) => {
      const hit = e.features?.[0];
      if (!hit) return;

      map.getCanvas().style.cursor = "pointer";

      // Teks keluhan datang dari basis data dan ditulis orang lain, jadi
      // ditempel lewat textContent - tidak pernah innerHTML.
      const box = document.createElement("div");
      const judul = document.createElement("strong");
      judul.textContent = String(hit.properties?.jenis ?? "keluhan fasilitas");
      const isi = document.createElement("span");
      isi.textContent = String(hit.properties?.keluhan ?? "");
      const usul = document.createElement("em");
      const bentuk = hit.properties?.usulan;
      usul.textContent = bentuk ? `Usulan: ${String(bentuk)}` : "Usulan belum baku";

      box.append(
        judul,
        document.createElement("br"),
        isi,
        document.createElement("br"),
        usul
      );
      popup.setLngLat(e.lngLat).setDOMContent(box).addTo(map);
    });

    map.on("mouseleave", "sponsorship-titik", () => {
      map.getCanvas().style.cursor = "";
      popup.remove();
    });

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

    if (!map || !mapReady || !map.getLayer("isochrone-fill")) return;

    // Pita disaring di peta, bukan dengan menarik ulang datanya. Ketiga
    // poligonnya sudah diambil sekaligus, jadi berganti pilihan tidak perlu
    // menunggu jaringan.
    const filter: maplibregl.FilterSpecification = [
      "in",
      ["get", "minutes"],
      ["literal", reachMinutes],
    ];

    map.setFilter("isochrone-fill", filter);
    map.setFilter("isochrone-line", filter);
  }, [mapReady, reachMinutes]);

  useEffect(() => {
    const map = mapRef.current;
    const source = map?.getSource("station-pois");

    if (!map || !mapReady || !source || !map.getLayer("poi-supply")) return;

    (source as maplibregl.GeoJSONSource).setData(pois ?? EMPTY_POLYGONS);

    const visibility = pois ? "visible" : "none";
    map.setLayoutProperty("poi-demand", "visibility", visibility);
    map.setLayoutProperty("poi-supply", "visibility", visibility);
  }, [mapReady, pois]);

  useEffect(() => {
    const map = mapRef.current;
    const source = map?.getSource("sponsorship");

    if (!map || !mapReady || !source || !map.getLayer("sponsorship-titik")) return;

    (source as maplibregl.GeoJSONSource).setData(sponsorship ?? EMPTY_POLYGONS);
    map.setLayoutProperty(
      "sponsorship-titik",
      "visibility",
      sponsorship ? "visible" : "none"
    );
  }, [mapReady, sponsorship]);

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
