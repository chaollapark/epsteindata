import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Header } from "@/components/header";
import { Footer } from "@/components/footer";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "The Epstein Files — EpsteinData.cc",
  description:
    "Search and explore the Jeffrey Epstein document archive. Full-text search across court filings, flight logs, and government records.",
  authors: [{ name: "EpsteinData.cc", url: "https://epsteindata.cc" }],
  openGraph: {
    siteName: "EpsteinData.cc",
    url: "https://epsteindata.cc",
    type: "website",
    title: "The Epstein Files — EpsteinData.cc",
    description:
      "Search and explore the Jeffrey Epstein document archive. Full-text search across court filings, flight logs, and government records.",
  },
  twitter: {
    card: "summary",
    site: "@epsteindata",
    title: "The Epstein Files — EpsteinData.cc",
    description:
      "Search and explore the Jeffrey Epstein document archive.",
  },
  alternates: {
    canonical: "https://epsteindata.cc",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <Header />
        <main>{children}</main>
        <Footer />
      </body>
    </html>
  );
}
