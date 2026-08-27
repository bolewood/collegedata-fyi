import type { Metadata } from "next";
import { Newsreader, Geist, JetBrains_Mono } from "next/font/google";
import { Analytics } from "@vercel/analytics/next";
import { Nav } from "@/components/Nav";
import { Footer } from "@/components/Footer";
import "./globals.css";

const newsreader = Newsreader({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  style: ["normal", "italic"],
  variable: "--font-newsreader",
  display: "swap",
});

const geist = Geist({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  variable: "--font-geist",
  display: "swap",
});

const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
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
        <Analytics />
      </body>
    </html>
  );
}
