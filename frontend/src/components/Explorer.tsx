"use client";

import { useCallback, useMemo, useState } from "react";

import AppHeader from "@/components/AppHeader";
import Assistant from "@/components/Assistant";
import ControlPanel from "@/components/ControlPanel";
import Map, { type FlyTarget } from "@/components/Map";
import StationPanel from "@/components/StationPanel";
import { useStationIsochrones } from "@/hooks/useStationIsochrones";
import { useStationPois } from "@/hooks/useStationPois";
import { bandMinutes, reachPoiMinutes, type ReachBand } from "@/lib/reach";
import { useStations } from "@/hooks/useStations";
import { KRL_LINES } from "@/lib/lines";
import { parseLines } from "@/types/station";
import type { StationCollection, StationFeature } from "@/types/station";

const VISIBLE_NETWORKS = ["KAI Commuter", "KAI"];

const SELECTED_ZOOM = 15;



export default function Explorer() {
  const { data, loading, error } = useStations();

  const [activeLines, setActiveLines] = useState<Set<string>>(
    () => new Set(KRL_LINES)
  );
  const [showLabels, setShowLabels] = useState(false);
  const [showSepi, setShowSepi] = useState(false);
  const [showIsochrone, setShowIsochrone] = useState(false);
  const [reachBand, setReachBand] = useState<ReachBand>("all");
  const [selected, setSelected] = useState<StationFeature | null>(null);
  const [flyTo, setFlyTo] = useState<FlyTarget | null>(null);

  const kaiData = useMemo<StationCollection | null>(() => {
    if (!data) return null;

    return {
      ...data,
      features: data.features.filter((feature) =>
        VISIBLE_NETWORKS.includes(feature.properties.network ?? "")
      ),
    };
  }, [data]);

  const shownData = useMemo<StationCollection | null>(() => {
    if (!kaiData) return null;
    if (activeLines.size === KRL_LINES.length) return kaiData;

    return {
      ...kaiData,
      features: kaiData.features.filter((feature) =>
        parseLines(feature.properties.lines).some((code) =>
          activeLines.has(code)
        )
      ),
    };
  }, [kaiData, activeLines]);

  const selectedId = typeof selected?.id === "number" ? selected.id : null;
  const isochrones = useStationIsochrones(selectedId, showIsochrone);
  const poiMinutes = reachPoiMinutes(reachBand);
  const pois = useStationPois(selectedId, poiMinutes, showIsochrone);

  const stations = shownData?.features ?? [];
  const kaiCount = kaiData?.features.length ?? 0;

  const handleSelect = useCallback((station: StationFeature) => {
    const [lon, lat] = station.geometry.coordinates;

    setSelected(station);
    setFlyTo({ lon, lat, minZoom: SELECTED_ZOOM, nonce: Date.now() });
  }, []);

  const handleToggleLine = useCallback((code: string) => {
    setActiveLines((prev) => {
      const next = new Set(prev);
      if (next.has(code)) {
        next.delete(code);
      } else {
        next.add(code);
      }
      return next;
    });
  }, []);

  return (
    <div className="flex h-full flex-col">
      <AppHeader stationCount={kaiCount} loading={loading} />

      <div className="flex min-h-0 flex-1">
        <div className="relative min-w-0 flex-1">
          <Map
            data={shownData}
            showLabels={showLabels}
            showSepi={showSepi}
            isochrones={isochrones}
            reachMinutes={bandMinutes(reachBand)}
            pois={pois}
            selected={selected}
            flyTo={flyTo}
            onSelect={handleSelect}
          />

          <div className="absolute left-3 top-3 z-10 max-h-[calc(100%-1.5rem)] overflow-y-auto">
            <ControlPanel
              stations={stations}
              loading={loading}
              error={error}
              onSelect={handleSelect}
              activeLines={activeLines}
              onToggleLine={handleToggleLine}
              showLabels={showLabels}
              onToggleLabels={setShowLabels}
              showSepi={showSepi}
              onToggleSepi={setShowSepi}
              showIsochrone={showIsochrone}
              onToggleIsochrone={setShowIsochrone}
              reachBand={reachBand}
              onReachBand={setReachBand}
              poiMinutes={poiMinutes}
              hasSelection={selectedId !== null}
            />
          </div>

          <Assistant station={selected} />
        </div>

        {selected && (
          <StationPanel station={selected} onClose={() => setSelected(null)} />
        )}
      </div>
    </div>
  );
}
