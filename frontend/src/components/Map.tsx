"use client";

import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

import { apiGet } from "@/lib/api";

export default function Map() {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    let cancelled = false;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: `https://v2.basemap.mapid.io/styles/street-v2.0/style.json?key=${process.env.NEXT_PUBLIC_MAPID_KEY}`,
      center: [106.8271129, -6.1754398], // lng, lat
      zoom: 11,
    });

    map.on("styleimagemissing", (e) => {
      if (map.hasImage(e.id)) return;
      map.addImage(e.id, { width: 1, height: 1, data: new Uint8Array(4) });
    });

    map.on("load", async () => {
      let data: GeoJSON.FeatureCollection;

      try {
        data = await apiGet<GeoJSON.FeatureCollection>(
          `/stations?type=${encodeURIComponent("KERETA API")}`
        );
      } catch (err) {
        console.error("Gagal memuat data stasiun:", err);
        return;
      }

      if (cancelled) return;

      map.addSource("stations", { type: "geojson", data });

      map.addLayer({
        id: "stations-circle",
        type: "circle",
        source: "stations",
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 10, 4, 16, 9],
          "circle-color": "#16a34a",
          "circle-stroke-width": 2,
          "circle-stroke-color": "#ffffff",
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
          "text-offset": [0, 1.2],
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

        const p = feature.properties as { name: string; kecamatan: string | null };

        new maplibregl.Popup()
          .setLngLat(e.lngLat)
          .setHTML(`<strong>${p.name}</strong><br/><small>${p.kecamatan ?? ""}</small>`)
          .addTo(map);
      });

      map.on("mouseenter", "stations-circle", () => {
        map.getCanvas().style.cursor = "pointer";
      });

      map.on("mouseleave", "stations-circle", () => {
        map.getCanvas().style.cursor = "";
      });
    });

    return () => {
      cancelled = true;
      map.remove();
    };
  }, []);

  return <div ref={containerRef} className="h-screen w-full" />;
}
