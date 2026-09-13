"use client";

import { useCallback, useMemo, useState } from "react";

import AppHeader from "@/components/AppHeader";
import Assistant from "@/components/Assistant";
import CompareCard from "@/components/CompareCard";
import ControlPanel from "@/components/ControlPanel";
import EksporModal from "@/components/EksporModal";
import PeringkatModal from "@/components/PeringkatModal";
import Map, { type FlyTarget } from "@/components/Map";
import StationPanel, { type Tab } from "@/components/StationPanel";
import type { FeatureCollection } from "geojson";
import { KELOMPOK_POI } from "@/lib/poi";
import { useLineRoutes } from "@/hooks/useLineRoutes";
import { useStationNaming } from "@/hooks/useStationNaming";
import { useStationIsochrones } from "@/hooks/useStationIsochrones";
import { useSponsorshipMarkers } from "@/hooks/useSponsorship";
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
  const [showSepi, setShowSepi] = useState(false);
  const [showIsochrone, setShowIsochrone] = useState(false);
  const [showSponsorship, setShowSponsorship] = useState(false);
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

  // Semua kelompok titik minat menyala secara bawaan; legenda yang mematikan.
  const [poiKelompok, setPoiKelompok] = useState<string[]>(() =>
    KELOMPOK_POI.map((k) => k.id)
  );
  const togglePoiKelompok = (id: string) =>
    setPoiKelompok((kini) =>
      kini.includes(id) ? kini.filter((x) => x !== id) : [...kini, id]
    );
  const routes = useLineRoutes();

  // Calon sponsor hanya diambil saat tab Naming benar-benar dibuka. Mengambilnya
  // di setiap pemilihan stasiun berarti satu permintaan jaringan untuk data yang
  // biasanya tidak dilihat siapa pun.
  const { naming } = useStationNaming(panelTab === "Naming" ? selectedId : null);
  const kandidatSponsor = useMemo<FeatureCollection | null>(() => {
    const daftar = naming?.kandidat_sponsor ?? [];
    if (panelTab !== "Naming" || daftar.length === 0) return null;
    return {
      type: "FeatureCollection",
      features: daftar.map((k, i) => ({
        type: "Feature",
        id: i,
        geometry: { type: "Point", coordinates: [k.lon, k.lat] },
        properties: {
          nama: k.nama,
          jenis: k.jenis,
          jarak_m: k.jarak_m,
          dalam_inti: k.dalam_inti,
        },
      })),
    };
  }, [naming, panelTab]);
  const sponsorship = useSponsorshipMarkers(showSponsorship);

  // Dua jendela yang berlaku untuk seluruh halaman, dibuka dari header.
  const [bukaEkspor, setBukaEkspor] = useState(false);
  const [bukaPeringkat, setBukaPeringkat] = useState(false);

  // Di telepon, panel kontrol melayang menutupi hampir seluruh peta, jadi ia
  // ditutup secara bawaan dan dibuka lewat tombol. Di layar lebar (sm ke atas)
  // ia selalu tampil lewat kelas `sm:block`, tak peduli nilai state ini.
  const [kontrolTerbuka, setKontrolTerbuka] = useState(false);

  // Titik katalog yang sedang dibuka rinciannya, disorot di peta. Disimpan di
  // sini - bukan di dalam halaman timbulnya - karena yang menggambarnya peta,
  // dan peta hidup satu tingkat di atas panel.
  const [sorotTitik, setSorotTitik] = useState<{
    lon: number;
    lat: number;
    nama: string;
  } | null>(null);

  const sorotKatalog = useCallback(
    (titik: { lon: number; lat: number; nama: string } | null) => {
      setSorotTitik(titik);
      if (titik) {
        // Zoom 16 supaya bangunan sekitarnya ikut terbaca; titik tanpa konteks
        // tidak menjawab pertanyaan "sebelah mana".
        setFlyTo({ lon: titik.lon, lat: titik.lat, minZoom: 16, nonce: Date.now() });
      }
    },
    []
  );

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
      <AppHeader
        stationCount={kaiCount}
        loading={loading}
        stationName={selected?.properties.name ?? null}
        onEkspor={() => setBukaEkspor(true)}
        onPeringkat={() => setBukaPeringkat(true)}
      />

      {bukaEkspor && (
        <EksporModal
          stationId={selectedId}
          stationName={selected?.properties.name ?? null}
          onClose={() => setBukaEkspor(false)}
        />
      )}

      {bukaPeringkat && (
        <PeringkatModal
          stasiunSorot={selected?.properties.name ?? null}
          onClose={() => setBukaPeringkat(false)}
        />
      )}

      <div className="flex min-h-0 flex-1">
        <div className="relative min-w-0 flex-1">
          <Map
            data={shownData}
            showSepi={showSepi}
            routes={routes}
            activeLines={Array.from(activeLines)}
            isochrones={isochrones}
            reachMinutes={bandMinutes(reachBand)}
            pois={pois}
            poiKelompok={poiKelompok}
            sponsorship={sponsorship}
            kandidatSponsor={kandidatSponsor}
            sorotTitik={sorotTitik}
            selected={selected}
            flyTo={flyTo}
            onSelect={handleSelect}
          />

          {/* Pemicu panel kontrol, hanya di telepon. */}
          {!kontrolTerbuka && (
            <button
              type="button"
              onClick={() => setKontrolTerbuka(true)}
              className="panel-float absolute left-3 top-3 z-10 flex items-center gap-2 border border-ink bg-panel px-3 py-2 text-xs font-semibold text-ink sm:hidden"
            >
              <FilterMark />
              Filter &amp; Layer
            </button>
          )}

          <div
            className={`absolute left-3 top-3 z-20 max-h-[calc(100%-1.5rem)] w-[calc(100vw-1.5rem)] max-w-[264px] overflow-y-auto sm:z-10 sm:w-auto sm:max-w-none ${
              kontrolTerbuka ? "block" : "hidden"
            } sm:block`}
          >
            {/* Tombol tutup, hanya di telepon. */}
            <button
              type="button"
              onClick={() => setKontrolTerbuka(false)}
              aria-label="Tutup panel kontrol"
              className="absolute right-2 top-2 z-10 border border-hair bg-panel px-1.5 py-0.5 text-xs leading-none text-ink-soft hover:border-ink hover:text-ink sm:hidden"
            >
              ✕
            </button>
            <ControlPanel
              stations={stations}
              loading={loading}
              error={error}
              onSelect={handleSelect}
              activeLines={activeLines}
              onToggleLine={handleToggleLine}
              showSepi={showSepi}
              onToggleSepi={setShowSepi}
              showIsochrone={showIsochrone}
              onToggleIsochrone={setShowIsochrone}
              showSponsorship={showSponsorship}
              onToggleSponsorship={setShowSponsorship}
              reachBand={reachBand}
              onReachBand={setReachBand}
              poiMinutes={poiMinutes}
              poiKelompok={poiKelompok}
              onPoiKelompokChange={togglePoiKelompok}
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
            onSorot={sorotKatalog}
            onClose={() => {
              setSelected(null);
              setPanelTab("Ikhtisar");
              setSorotTitik(null);
            }}
          />
        )}
      </div>
    </div>
  );
}

function FilterMark() {
  return (
    <svg
      viewBox="0 0 24 24"
      width="14"
      height="14"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M3 5h18M6 12h12M10 19h4" />
    </svg>
  );
}
