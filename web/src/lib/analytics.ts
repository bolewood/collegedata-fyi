"use client";

import { track } from "@vercel/analytics";

type AnalyticsValue = string | number | boolean | null | undefined;
export type AnalyticsProperties = Record<string, AnalyticsValue>;

export function trackEvent(name: string, properties?: AnalyticsProperties) {
  try {
    track(name, properties);
  } catch {
    // Analytics should never block navigation, local storage, copy, or downloads.
  }
}

export function trackSchoolSearchSelected(properties: {
  surface: "home" | "header";
  schoolId: string;
  coverageStatus?: string | null;
  latestCdsYear?: string | null;
  queryLength: number;
  resultCount: number;
  inputMethod: "keyboard" | "mouse";
}) {
  trackEvent("school_search_selected", {
    surface: properties.surface,
    school_id: properties.schoolId,
    coverage_status: properties.coverageStatus,
    latest_cds_year: properties.latestCdsYear,
    query_length: properties.queryLength,
    result_count: properties.resultCount,
    input_method: properties.inputMethod,
  });
}

export function trackSourceOpened(properties: {
  surface: string;
  schoolId?: string | null;
  cdsYear?: string | null;
  sourceFormat?: string | null;
  action?: "download" | "view_source" | "open_archive";
}) {
  trackEvent("source_opened", {
    surface: properties.surface,
    school_id: properties.schoolId,
    cds_year: properties.cdsYear,
    source_format: properties.sourceFormat,
    action: properties.action ?? "open_archive",
  });
}

export function trackDownload(properties: {
  surface: string;
  fileType: string;
  item?: string | null;
  rowCount?: number | null;
}) {
  trackEvent("download_clicked", {
    surface: properties.surface,
    file_type: properties.fileType,
    item: properties.item,
    row_count: properties.rowCount,
  });
}

