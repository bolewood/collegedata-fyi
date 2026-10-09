import { ROBOTS_TXT } from "@/lib/robots-txt";

export const dynamic = "force-static";

export function GET() {
  return new Response(ROBOTS_TXT, {
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
    },
  });
}
