import type { Metadata } from "next";
import { Archivo, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";

// Archivo dipilih karena hurufnya tegas dan agak editorial. Dipakai untuk
// judul dan teks yang dibaca mengalir.
const archivo = Archivo({
  variable: "--font-archivo",
  subsets: ["latin"],
  display: "swap",
});

// Pasangannya mono, khusus buat label seksi, kode, dan angka. Perangkat
// analisis sungguhan hampir selalu memisahkan keduanya, dan pemisahan itu
// yang bikin tampilannya terasa disusun orang, bukan ditempel seadanya.
const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "StaSIUN — Station Spatial Intelligence for Urban Network",
  description:
    "Peta dan analisis potensi ruang komersial stasiun KAI Commuter di DKI Jakarta.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="id"
      className={`${archivo.variable} ${plexMono.variable} h-full antialiased`}
    >
      <body className="h-full">{children}</body>
    </html>
  );
}
