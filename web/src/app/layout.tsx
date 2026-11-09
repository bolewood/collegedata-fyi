import type { Metadata } from "next";
import localFont from "next/font/local";
import { PrivateAnalytics } from "@/components/PrivateAnalytics";
import { Nav } from "@/components/Nav";
import { Footer } from "@/components/Footer";
import "./globals.css";

// Self-hosted (see ./fonts/README.md): next/font/google fetched these from
// Google on every build, and a failed fetch failed the whole Vercel build.
const newsreader = localFont({
  src: [
    { path: "./fonts/newsreader-latin-wght-normal.woff2", weight: "200 800", style: "normal" },
    { path: "./fonts/newsreader-latin-wght-italic.woff2", weight: "200 800", style: "italic" },
  ],
  variable: "--font-newsreader",
  display: "swap",
});

const geist = localFont({
  src: "./fonts/geist-latin-wght-normal.woff2",
  weight: "100 900",
  style: "normal",
  variable: "--font-geist",
  display: "swap",
});

const jetbrains = localFont({
  src: "./fonts/jetbrains-mono-latin-wght-normal.woff2",
  weight: "100 800",
  style: "normal",
  variable: "--font-jetbrains",
  display: "swap",
});

// metadataBase lets every route segment below use relative paths for
// canonical / openGraph URLs. The apex (https://collegedata.fyi)
// 301-redirects to www, so www is the canonical host.
export const metadata: Metadata = {
  metadataBase: new URL("https://www.collegedata.fyi"),
  title: {
    default: "collegedata.fyi — Free college data, straight from the source",
    template: "%s | collegedata.fyi",
  },
  description:
    "The most comprehensive free college data we know of — the report each college publishes, plus the government’s own numbers, in one public place.",
  alternates: {
    canonical: "/",
  },
  openGraph: {
    title: "collegedata.fyi — Free college data, straight from the source",
    description:
      "The most comprehensive free college data we know of — the report each college publishes, plus the government’s own numbers, in one public place.",
    url: "/",
    siteName: "collegedata.fyi",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const fontVars = `${newsreader.variable} ${geist.variable} ${jetbrains.variable}`;
  return (
    <html lang="en" className={`h-full antialiased ${fontVars}`}>
      <body className="cd-theme min-h-full flex flex-col">
        <Nav />
        <main className="flex-1">{children}</main>
        <Footer />
        <PrivateAnalytics />
      </body>
    </html>
  );
}
