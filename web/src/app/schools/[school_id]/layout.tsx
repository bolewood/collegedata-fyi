import type { ReactNode } from "react";
import { notFound } from "next/navigation";
import { SchoolApiNote } from "@/components/SchoolApiNote";
import { isRoutableSchoolSlug } from "@/lib/school-cache-tags";
import { cachedSchoolInks, schoolInkWrapperProps } from "@/lib/school-inks";

export const dynamic = "force-static";
export const revalidate = 86400;

export default async function SchoolRecordLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ school_id: string }>;
}) {
  const { school_id } = await params;
  // A slug with characters no school can have: 404 before reading any data.
  if (!isRoutableSchoolSlug(school_id)) notFound();
  const inks = await cachedSchoolInks(school_id);
  return (
    <div {...schoolInkWrapperProps(inks)}>
      {children}
      <SchoolApiNote />
    </div>
  );
}
