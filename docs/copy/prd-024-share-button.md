# PRD 024 M1: Share button copy deck

Every new user-visible string. Owner reads before ship.

| String | Where it appears |
|---|---|
| Share | Button label, school, year, coverage, and Match pages |
| Copied | Same button for about 1.6 s after a copy |
| Share this section | Screen-reader label for the icon-only variant (unused in M1) |
| Share options | Screen-reader label for the popover |
| Copy link | Popover item |
| Copy summary | Popover item, Match page only |
| Share with device | Popover item, only when the browser supports native share |
| Copy this link | Label of the selectable URL field, shown only if copying fails |
| Link copied / Summary copied | Screen-reader announcement after a copy |
| Anyone with this link can open this Match profile. | Popover note, Match page |
| {School} Common Data Set archive | Title passed to device share, school page |
| Source-linked admissions, enrollment, aid, and CDS documents from CollegeData.fyi. | Text passed to device share, school and year pages |
| {School} Common Data Set {year} | Title passed to device share, year page |
| CollegeData.fyi match list | Title passed to device share, Match page |
| CollegeData.fyi CDS coverage view | Title passed to device share, coverage page |
| CollegeData.fyi Match List Builder | Open Graph / Twitter title, /match |
| Build a college match list from the numbers schools publish. | Open Graph / Twitter description, /match |

## Copied summary text (Match, "Copy summary")

```
CollegeData.fyi Match
42 schools ranked

Strong fit   █████        8
Above range  ███          5
In range     ██████████  15
Below range  ██████       9
Unknown      ███          5

https://www.collegedata.fyi/match
```

Empty result: `CollegeData.fyi Match` / `No schools ranked yet` / the link.
The link is the generic /match page. It carries no code, per the brief; "Copy link" shares the profile.
