import type { Metadata } from "next";
import { Analytics } from "@vercel/analytics/next";
import { Nav } from "@/components/Nav";
import { Footer } from "@/components/Footer";
import "./globals.css";

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
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col bg-white text-gray-900">
        <Nav />
        <main className="flex-1">{children}</main>
        <Footer />
        <Analytics />
      </body>
    </html>
  );
}
