import type { ReactNode } from "react";
import { SchoolApiNote } from "@/components/SchoolApiNote";
import { cachedSchoolInks, schoolInkWrapperProps } from "@/lib/school-inks";

export const dynamic = "force-static";
export const revalidate = 3600;

export default async function SchoolRecordLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ school_id: string }>;
}) {
  const { school_id } = await params;
  const inks = await cachedSchoolInks(school_id);
  return (
    <div {...schoolInkWrapperProps(inks)}>
      {children}
      <SchoolApiNote />
    </div>
  );
}
