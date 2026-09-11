"use client";

import { useCallback, useMemo, useState } from "react";

import AppHeader from "@/components/AppHeader";
import Assistant from "@/components/Assistant";
import CompareCard from "@/components/CompareCard";
import ControlPanel from "@/components/ControlPanel";
import Map, { type FlyTarget } from "@/components/Map";
import StationPanel, { type Tab } from "@/components/StationPanel";
import { useStationIsochrones } from "@/hooks/useStationIsochrones";
import { useStationPois } from "@/hooks/useStationPois";
import { bandMinutes, reachPoiMinutes, type ReachBand } from "@/lib/reach";
import { useStations } from "@/hooks/useStations";
import { KRL_LINES } from "@/lib/lines";
import { parseLines } from "@/types/station";
import type { AksiAsisten, StationCollection, StationFeature } from "@/types/station";

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
  const [panelTab, setPanelTab] = useState<Tab>("Ikhtisar");
  const [compareIds, setCompareIds] = useState<number[] | null>(null);
  const [simulasiPreset, setSimulasiPreset] = useState<{
    bobot: Record<string, number>;
    nonce: number;
  } | null>(null);

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

  // Dicari di seluruh stasiun KAI, bukan hanya yang lolos filter line. Tombol
  // asisten tidak boleh mati hanya karena line stasiunnya sedang disembunyikan.
  const stationById = useMemo(() => {
    const peta: Record<number, StationFeature> = {};
    for (const f of kaiData?.features ?? []) {
      if (typeof f.id === "number") peta[f.id] = f;
    }
    return peta;
  }, [kaiData]);

  const namaStasiun = useMemo(
    () =>
      Object.fromEntries(
        Object.entries(stationById).map(([id, f]) => [id, f.properties.name])
      ) as Record<number, string>,
    [stationById]
  );

  const openStation = useCallback(
    (stationId: number, tab: Tab = "Ikhtisar") => {
      const station = stationById[stationId];
      if (!station) return;
      handleSelect(station);
      setPanelTab(tab);
    },
    [stationById, handleSelect]
  );

  /**
   * Penerima tombol dari jawaban asisten. Tiap jenis aksi dipetakan ke
   * perubahan state yang sama dengan yang dilakukan pengguna lewat klik -
   * asisten tidak punya jalur pintas ke tampilan.
   */
  const handleAction = useCallback(
    (aksi: AksiAsisten) => {
      if (aksi.jenis === "buka_stasiun" && aksi.station_id != null) {
        const tab = (["Ikhtisar", "Ad-Space", "Tenant", "Naming"] as const).find(
          (t) => t === aksi.tab
        );
        openStation(aksi.station_id, tab ?? "Ikhtisar");
      } else if (aksi.jenis === "bandingkan" && aksi.station_ids?.length) {
        setCompareIds(aksi.station_ids);
      } else if (aksi.jenis === "simulasi" && aksi.station_id != null && aksi.bobot) {
        openStation(aksi.station_id, "Ikhtisar");
        setSimulasiPreset({ bobot: aksi.bobot, nonce: Date.now() });
      }
    },
    [openStation]
  );

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

          {compareIds && (
            <CompareCard
              stationIds={compareIds}
              names={namaStasiun}
              onOpen={(id) => openStation(id)}
              onClose={() => setCompareIds(null)}
            />
          )}

          <Assistant station={selected} onAction={handleAction} />
        </div>

        {selected && (
          <StationPanel
            station={selected}
            tab={panelTab}
            onTabChange={setPanelTab}
            simulasiPreset={simulasiPreset}
            onClose={() => {
              setSelected(null);
              setPanelTab("Ikhtisar");
            }}
          />
        )}
      </div>
    </div>
  );
}
