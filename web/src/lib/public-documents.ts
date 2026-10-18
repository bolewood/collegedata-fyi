/** Quality flags omitted from public school, year, and manifest listings.

blank_template rows stay in cds_documents / PostgREST for transparency.
To hide a row from the public API as well, set removed_at from main
after merge (not from a feature branch):

  update cds_documents
     set removed_at = now()
   where id = '<document_id>'
     and data_quality_flag = 'blank_template';
*/
export const PUBLIC_HIDDEN_QUALITY_FLAGS = ["blank_template"] as const;

export type PublicQualityFlag = (typeof PUBLIC_HIDDEN_QUALITY_FLAGS)[number];

export function isPubliclyListedDocument(doc: {
  data_quality_flag?: string | null;
}): boolean {
  const flag = doc.data_quality_flag ?? "";
  return !(PUBLIC_HIDDEN_QUALITY_FLAGS as readonly string[]).includes(flag);
}

export function excludeHiddenQualityDocuments<
  T extends { data_quality_flag?: string | null },
>(docs: T[]): T[] {
  return docs.filter(isPubliclyListedDocument);
}
