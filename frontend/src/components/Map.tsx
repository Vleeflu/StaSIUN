"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

import StationSearch from "@/components/StationSearch";
import { useStations } from "@/hooks/useStations";
import { FALLBACK_COLOR, LINE_COLOR, lineLabel } from "@/lib/lines";
import { parseLines } from "@/types/station";
import type { StationFeature, StationProps } from "@/types/station";

const STYLE_URL = `https://v2.basemap.mapid.io/styles/street-v2.0/style.json?key=${process.env.NEXT_PUBLIC_MAPID_KEY}`;
const PUSAT_JAKARTA: [number, number] = [106.8271129, -6.1754398];
const ZOOM_AWAL = 11;
const ZOOM_TERPILIH = 18;

const ICON_SIZE = 60;

function createPieIcon(colors: string[]): ImageData {
  const canvas = document.createElement("canvas");
  canvas.width = ICON_SIZE;
  canvas.height = ICON_SIZE;

  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Canvas 2D tidak tersedia");

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

function buatIsiPopup(props: StationProps): HTMLElement {
  const wrapper = document.createElement("div");

  const judul = document.createElement("strong");
  judul.textContent = props.code ? `${props.name} (${props.code})` : props.name;
  wrapper.appendChild(judul);

  const lines = parseLines(props.lines);
  const subtitle =
    lines.length > 0
      ? `Lin ${lineLabel(lines)}`
      : props.kecamatan;

  if (subtitle) {
    wrapper.appendChild(document.createElement("br"));
    const small = document.createElement("small");
    small.textContent = subtitle;
    wrapper.appendChild(small);
  }

  return wrapper;
}

export default function Map() {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const popupRef = useRef<maplibregl.Popup | null>(null);

  const [mapReady, setMapReady] = useState(false);
  const { data, stations, loading, error } = useStations();

  const tampilkanPopup = useCallback(
    (lngLat: maplibregl.LngLatLike, props: StationProps) => {
      const map = mapRef.current;
      if (!map) return;

      popupRef.current?.remove();
      popupRef.current = new maplibregl.Popup({
        offset: 12,
        className: "stasiun-popup",
        focusAfterOpen: false,
      })
        .setLngLat(lngLat)
        .setDOMContent(buatIsiPopup(props))
        .addTo(map);
    },
    []
  );

  useEffect(() => {
    if (!containerRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: STYLE_URL,
      center: PUSAT_JAKARTA,
      zoom: ZOOM_AWAL,
    });
    mapRef.current = map;

    map.addControl(new maplibregl.NavigationControl(), "top-right");

    map.on("styleimagemissing", (e) => {
      if (map.hasImage(e.id)) return;
      map.addImage(e.id, { width: 1, height: 1, data: new Uint8Array(4) });
    });

    map.on("load", () => setMapReady(true));

    return () => {
      popupRef.current?.remove();
      popupRef.current = null;
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
      },
      paint: {
        "text-color": "#0f172a",
        "text-halo-color": "#ffffff",
        "text-halo-width": 1.5,
      },
    });

    map.on("click", "stations-circle", (e) => {
      const feature = e.features?.[0];
      if (!feature) return;
      tampilkanPopup(e.lngLat, feature.properties as StationProps);
    });

    map.on("mouseenter", "stations-circle", () => {
      map.getCanvas().style.cursor = "pointer";
    });

    map.on("mouseleave", "stations-circle", () => {
      map.getCanvas().style.cursor = "";
    });
  }, [mapReady, data, tampilkanPopup]);

  const handleSelect = useCallback(
    (station: StationFeature) => {
      const map = mapRef.current;
      if (!map) return;

      const [lon, lat] = station.geometry.coordinates;
      map.flyTo({ center: [lon, lat], zoom: ZOOM_TERPILIH, duration: 1200 });
      tampilkanPopup([lon, lat], station.properties);
    },
    [tampilkanPopup]
  );

  return (
    <div className="relative h-screen w-full">
      <div ref={containerRef} className="h-full w-full" />

      <div className="absolute left-4 top-4 z-10">
        <StationSearch
          stations={stations}
          loading={loading}
          error={error}
          onSelect={handleSelect}
        />
      </div>
    </div>
  );
}
