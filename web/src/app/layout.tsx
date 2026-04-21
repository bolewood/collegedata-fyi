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
// 307-redirects to www, so www is the canonical host.
export const metadata: Metadata = {
  metadataBase: new URL("https://www.collegedata.fyi"),
  title: {
    default: "collegedata.fyi - Common Data Set Archive",
    template: "%s | collegedata.fyi",
  },
  description:
    "An open-source archive of U.S. college Common Data Set documents. Browse admissions, enrollment, financial aid, and more across hundreds of schools.",
  alternates: {
    canonical: "/",
  },
  openGraph: {
    title: "collegedata.fyi",
    description: "Open-source Common Data Set archive for U.S. colleges",
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
