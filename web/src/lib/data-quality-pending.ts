/**
 * Runs in the browser before hydration, against a static page that shows the default year. For a direct link to another
 * year it only sets attributes (`data-dq-pending` on #dq-shell, `aria-busy` on #dq-body); text and layout come from CSS and
 * from markup the server already rendered, because changing the page's content here would itself be a hydration mismatch.
 * `others` are the years other than the one the static HTML shows.
 */
export function pendingYearScript(others: string[]): string {
  return `(function(){var y=new URLSearchParams(location.search).get("year");if(!y||${JSON.stringify(others)}.indexOf(y)<0)return;var b=document.getElementById("dq-body"),s=document.getElementById("dq-shell");if(!b||!s)return;s.setAttribute("data-dq-pending",y);b.setAttribute("aria-busy","true");})();`;
}
