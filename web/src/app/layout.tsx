import type { Metadata } from "next";
import localFont from "next/font/local";
import { PrivateAnalytics } from "@/components/PrivateAnalytics";
import { Nav } from "@/components/Nav";
import { Footer } from "@/components/Footer";
import "./globals.css";
import { SITE_NAME, SITE_ORIGIN } from "@/lib/site";

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
// canonical / openGraph URLs. The apex (https://quadfile.org)
// 301-redirects to www, so www is the canonical host.
export const metadata: Metadata = {
  metadataBase: new URL(SITE_ORIGIN),
  title: {
    default: `${SITE_NAME} — Free college data, straight from the source`,
    template: `%s | ${SITE_NAME}`,
  },
  description:
    "Admissions, test scores, financial aid, and graduate outcomes for U.S. colleges, from published school reports and federal records, with original files linked.",
  alternates: {
    canonical: "/",
  },
  openGraph: {
    title: `${SITE_NAME} — Free college data, straight from the source`,
    description:
      "Admissions, test scores, financial aid, and graduate outcomes for U.S. colleges, from published school reports and federal records, with original files linked.",
    url: "/",
    siteName: SITE_NAME,
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
