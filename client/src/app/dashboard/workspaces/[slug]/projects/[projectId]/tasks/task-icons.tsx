export default function TaskIcon({
  name,
}: {
  name:
    | "chevron-down"
    | "comment"
    | "search"
    | "filter"
    | "calendar"
    | "board"
    | "list"
    | "trash"
    | "tasks"
    | "move";
}) {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {name === "chevron-down" && <path d="m6 8 4 4 4-4" />}
      {name === "comment" && <path d="M3 3.5h14v10H8l-5 3z" />}
      {name === "search" && (
        <>
          <circle cx="8.5" cy="8.5" r="5.5" />
          <path d="m13 13 4 4" />
        </>
      )}
      {name === "filter" && <path d="M2.5 3.5h15L12 10v6l-4 2v-8Z" />}
      {name === "calendar" && (
        <>
          <rect x="2.5" y="4" width="15" height="13" rx="2" />
          <path d="M6 2v4m8-4v4M3 8h14" />
        </>
      )}
      {name === "board" && (
        <>
          <rect x="2" y="2.5" width="16" height="15" rx="2" />
          <path d="M7.5 3v14m5-14v14" />
        </>
      )}
      {name === "list" && (
        <>
          <path d="M7 4h10M7 10h10M7 16h10" />
          <circle cx="3" cy="4" r=".5" />
          <circle cx="3" cy="10" r=".5" />
          <circle cx="3" cy="16" r=".5" />
        </>
      )}
      {name === "trash" && (
        <>
          <path d="M3 5h14M7 5V2.5h6V5M5 5l.8 12h8.4L15 5M8 8v6m4-6v6" />
        </>
      )}
      {name === "tasks" && (
        <>
          <path d="m2.5 4.5 1.5 1.5 3-3m2 2h8m-14.5 5 1.5 1.5 3-3m2 2h8m-14.5 5 1.5 1.5 3-3m2 2h8" />
        </>
      )}
      {name === "move" && (
        <>
          <path d="M10 2v16M2 10h16M7 5l3-3 3 3M7 15l3 3 3-3M5 7l-3 3 3 3m10-6 3 3-3 3" />
        </>
      )}
    </svg>
  );
}
