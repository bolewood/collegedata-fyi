# Copy deck: campuses covered (or not) by another campus's filing

Persona: parents and students first. A student looking up a branch campus
should learn in one sentence why there is no school report here and where the
nearest one is, and still get that campus's federal numbers.

Implemented in `web/src/lib/campus-filings.ts`. Awaiting Anthony's read.

## 1. Branch page, main campus files a report that does not include it

Shown in the card at the top of the page, in place of "We haven't found a
Common Data Set from this school."

> We haven't found a Common Data Set for this campus. Miami University-Oxford
> publishes one, and it does not include this campus. [See Miami
> University-Oxford]. The federal numbers for this campus are below.

"campus" becomes "school" or "program" where that reads truer (Middlebury
Institute at Monterey, Northeastern University Professional Programs). The
last sentence is dropped when we have no federal numbers.

Applies to: Miami Hamilton and Middletown; the seven Kent State regional
campuses; Northeastern Professional Programs; Middlebury Institute at
Monterey; Drury College of Continuing
Professional Studies; Northwest University Center for Online and Extended
Education.

## 2. Campus page, one filing covers several campuses together

Shown as the small italic note under the page lead, on the school page and
each year page.

> Fairleigh Dickinson University publishes one Common Data Set for its Florham
> and Metropolitan campuses together. The numbers from the school's report on
> this page cover both; the federal numbers are for this campus alone.

Applies to: Fairleigh Dickinson Florham and Metropolitan.

## Not said

- How we found out (identical files, federal comparison). That is operator
  detail and lives in the audit tool.
- Anything about the branch being lesser. The page still leads with its own
  federal numbers.
