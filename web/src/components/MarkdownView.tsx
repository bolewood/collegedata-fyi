"use client";

import { useState, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export function MarkdownView({
  markdown,
  schoolName,
  year,
}: {
  markdown: string;
  schoolName: string;
  year: string;
}) {
  const [expanded, setExpanded] = useState(false);

  const handleDownload = useCallback(() => {
    const blob = new Blob([markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${schoolName.replace(/\s+/g, "_")}_${year}_cds.md`;
    a.click();
    URL.revokeObjectURL(url);
  }, [markdown, schoolName, year]);

  return (
    <div className="mt-8">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900">
          Source Document
        </h3>
        <button
          onClick={handleDownload}
          className="text-sm text-blue-600 hover:text-blue-800"
        >
          Download .md
        </button>
      </div>

      {!expanded ? (
        <button
          onClick={() => setExpanded(true)}
          className="w-full rounded-lg border border-gray-200 px-4 py-3 text-sm text-gray-600 hover:bg-gray-50 text-left"
        >
          Show full document ({Math.round(markdown.length / 1024)} KB)
        </button>
      ) : (
        <>
          <button
            onClick={() => setExpanded(false)}
            className="mb-4 text-sm text-gray-500 hover:text-gray-700"
          >
            Collapse
          </button>
          <div className="rounded-lg border border-gray-200 p-6 overflow-x-auto">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={markdownComponents}
            >
              {markdown}
            </ReactMarkdown>
          </div>
        </>
      )}
    </div>
  );
}

const markdownComponents = {
  h1: ({ children, ...props }: React.ComponentProps<"h1">) => (
    <h1 className="text-2xl font-bold text-gray-900 mt-8 mb-3" {...props}>
      {children}
    </h1>
  ),
  h2: ({ children, ...props }: React.ComponentProps<"h2">) => (
    <h2
      className="text-xl font-semibold text-gray-900 mt-6 mb-2 border-b border-gray-200 pb-1"
      {...props}
    >
      {children}
    </h2>
  ),
  h3: ({ children, ...props }: React.ComponentProps<"h3">) => (
    <h3 className="text-lg font-semibold text-gray-900 mt-4 mb-2" {...props}>
      {children}
    </h3>
  ),
  p: ({ children, ...props }: React.ComponentProps<"p">) => (
    <p className="text-sm text-gray-700 mb-2 leading-relaxed" {...props}>
      {children}
    </p>
  ),
  ul: ({ children, ...props }: React.ComponentProps<"ul">) => (
    <ul className="text-sm text-gray-700 mb-2 ml-4 list-disc" {...props}>
      {children}
    </ul>
  ),
  ol: ({ children, ...props }: React.ComponentProps<"ol">) => (
    <ol className="text-sm text-gray-700 mb-2 ml-4 list-decimal" {...props}>
      {children}
    </ol>
  ),
  li: ({ children, ...props }: React.ComponentProps<"li">) => (
    <li className="mb-0.5" {...props}>
      {children}
    </li>
  ),
  table: ({ children, ...props }: React.ComponentProps<"table">) => (
    <div className="overflow-x-auto mb-4">
      <table
        className="min-w-full text-sm border-collapse border border-gray-200"
        {...props}
      >
        {children}
      </table>
    </div>
  ),
  thead: ({ children, ...props }: React.ComponentProps<"thead">) => (
    <thead className="bg-gray-50" {...props}>
      {children}
    </thead>
  ),
  th: ({ children, ...props }: React.ComponentProps<"th">) => (
    <th
      className="border border-gray-200 px-3 py-1.5 text-left font-medium text-gray-900"
      {...props}
    >
      {children}
    </th>
  ),
  td: ({ children, ...props }: React.ComponentProps<"td">) => (
    <td className="border border-gray-200 px-3 py-1.5 text-gray-700" {...props}>
      {children}
    </td>
  ),
  a: ({ children, href, ...props }: React.ComponentProps<"a">) => (
    <a
      href={href}
      className="text-blue-600 hover:text-blue-800"
      target="_blank"
      rel="noopener noreferrer"
      {...props}
    >
      {children}
    </a>
  ),
  hr: (props: React.ComponentProps<"hr">) => (
    <hr className="my-4 border-gray-200" {...props} />
  ),
  blockquote: ({ children, ...props }: React.ComponentProps<"blockquote">) => (
    <blockquote
      className="border-l-4 border-gray-200 pl-4 text-sm text-gray-600 my-2"
      {...props}
    >
      {children}
    </blockquote>
  ),
  code: ({ children, ...props }: React.ComponentProps<"code">) => (
    <code
      className="bg-gray-100 rounded px-1 py-0.5 text-xs text-gray-800"
      {...props}
    >
      {children}
    </code>
  ),
};
