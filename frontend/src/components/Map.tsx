"use client";

import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

import { FALLBACK_COLOR, LINE_COLOR } from "@/lib/lines";
import type { StationCollection, StationFeature } from "@/types/station";

const STYLE_URL = `https://v2.basemap.mapid.io/styles/street-v2.0/style.json?key=${process.env.NEXT_PUBLIC_MAPID_KEY}`;

const JAKARTA_CENTER: [number, number] = [106.8271129, -6.1754398];
const INITIAL_ZOOM = 11;

const ICON_SIZE = 60;

const EMPTY: StationCollection = { type: "FeatureCollection", features: [] };

export type FlyTarget = {
  lon: number;
  lat: number;
  minZoom: number;
  nonce: number;
};

type Props = {
  data: StationCollection | null;
  showLabels: boolean;
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
  selected,
  flyTo,
  onSelect,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);

  // Handler klik dipasang sekali seumur peta, jadi ia harus membaca data dan
  // callback terbaru lewat ref — bukan lewat closure yang keburu basi.
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
      // Kredit bawaan mendarat di kanan bawah, tepat di bawah tombol asisten.
      // Dimatikan di sini lalu dipasang ulang di kiri bawah dalam bentuk ringkas.
      attributionControl: false,
    });

    mapRef.current = map;

    map.addControl(new maplibregl.NavigationControl(), "bottom-left");

    // Kredit peta wajib tetap ada — lisensi OpenStreetMap dan ketentuan MAPID
    // mengharuskannya. Mode ringkas menyusutkannya jadi satu tombol info.
    map.addControl(
      new maplibregl.AttributionControl({ compact: true }),
      "bottom-left"
    );

    // Sprite MAPID tidak punya sebagian ikon yang dipanggil style-nya sendiri.
    // Kita sodorkan gambar kosong 1x1 supaya konsol tidak penuh error.
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

    // Lebar peta berubah tiap panel stasiun dibuka atau ditutup. Tanpa ini
    // kanvasnya tetap seukuran lama dan petanya kelihatan melar.
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

    // Cincin penanda digambar lebih dulu supaya berada di bawah ikon stasiun.
    map.addLayer({
      id: "selected-ring",
      type: "circle",
      source: "selected-station",
      paint: {
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 10, 14, 18, 32],
        "circle-color": "#ec3013",
        "circle-opacity": 0.12,
        "circle-stroke-width": 2,
        "circle-stroke-color": "#ec3013",
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

    map.on("click", "stations-circle", (e) => {
      const hit = e.features?.[0];
      const collection = dataRef.current;

      if (!hit || !collection) return;

      // Properti dari event MapLibre sudah diserialisasi, jadi fitur aslinya
      // dicari balik lewat id supaya panel menerima data yang utuh.
      const match = collection.features.find((f) => f.id === hit.id);

      if (match) selectRef.current(match);
    });

    map.on("mouseenter", "stations-circle", () => {
      map.getCanvas().style.cursor = "pointer";
    });

    map.on("mouseleave", "stations-circle", () => {
      map.getCanvas().style.cursor = "";
    });
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
    const source = map?.getSource("selected-station");

    if (!source) return;

    (source as maplibregl.GeoJSONSource).setData(
      selected ? { type: "FeatureCollection", features: [selected] } : EMPTY
    );
  }, [mapReady, selected]);

  useEffect(() => {
    const map = mapRef.current;

    if (!map || !flyTo) return;

    // Cuma mendekat, tidak pernah menjauh. Kalau user sudah zoom lebih dalam
    // dari minZoom, tampilannya dibiarkan apa adanya.
    map.flyTo({
      center: [flyTo.lon, flyTo.lat],
      zoom: Math.max(map.getZoom(), flyTo.minZoom),
      duration: 1200,
    });
  }, [flyTo]);

  return <div ref={containerRef} className="h-full w-full" />;
}
