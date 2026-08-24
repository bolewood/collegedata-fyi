import type { ReactNode } from "react";
import { cachedSchoolInks, schoolInkWrapperProps } from "@/lib/school-inks";

export default async function SchoolRecordLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ school_id: string }>;
}) {
  const { school_id } = await params;
  const inks = await cachedSchoolInks(school_id);
  return <div {...schoolInkWrapperProps(inks)}>{children}</div>;
}
