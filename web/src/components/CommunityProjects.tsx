import { communityProjects } from "@/data/community/projects";
import { CommunityLink } from "./CommunityInvitation";
export function CommunityProjects() {
  const references = communityProjects.filter(
    (p) => p.kind === "public_reference",
  );
  const stories = communityProjects.filter((p) => p.kind === "approved_story");
  return (
    <section
      id="projects"
      className="usage-band"
      aria-labelledby="community-projects"
    >
      <h2 id="community-projects">Projects using the data</h2>
      <p className="my-4">
        Some of the ways people are putting the data to work. Public references
        link to the project&apos;s own documentation. Stories shared with us are
        published with the sender&apos;s approval.
      </p>
      <h3 className="serif text-xl">Public project references</h3>
      <ul>
        {references.map((p) => (
          <li key={p.slug} className="border-b border-[var(--rule)] py-4">
            <a href={p.url}>{p.name}</a>
            <p className="my-2 text-sm">{p.description}</p>
            <p className="text-xs">
              <a href={p.evidenceUrl}>Supporting source</a> · Checked{" "}
              {p.checked}
            </p>
          </li>
        ))}
      </ul>
      {stories.length > 0 && (
        <>
          <h3 className="serif mt-6 text-xl">Stories shared with us</h3>
          {stories.map((p) => (
            <article key={p.slug}>
              <h4>
                <a href={p.url}>{p.name}</a>
              </h4>
              <p>{p.description}</p>
              {p.kind === "approved_story" && (
                <>
                  <p>{p.credit}</p>
                  {p.quote && <blockquote>{p.quote}</blockquote>}
                </>
              )}
            </article>
          ))}
        </>
      )}
      <p className="my-5">
        <CommunityLink surface="usage" kind="story">
          Using the data in a different way? Tell us about it.
        </CommunityLink>
      </p>
      <p className="text-xs">
        Usage statistics are CC0. Curated project write-ups are{" "}
        <a href="https://creativecommons.org/licenses/by-sa/4.0/">
          CC BY-SA 4.0
        </a>
        . Linked projects and their content keep their own terms.
      </p>
    </section>
  );
}
