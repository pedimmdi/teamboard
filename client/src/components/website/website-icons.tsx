import type { SVGProps } from "react";

const paths = {
  arrow: <path d="M4 12h15m-6-6 6 6-6 6" />,
  board: <><rect x="3" y="4" width="18" height="16" rx="3" /><path d="M9 4v16m6-16v16" /></>,
  chat: <path d="M21 11.5a8.5 8.5 0 0 1-8.5 8.5H4l1.7-4A8.5 8.5 0 1 1 21 11.5ZM8 11.5h8" />,
  calendar: <><rect x="3" y="5" width="18" height="16" rx="3" /><path d="M7 3v4m10-4v4M3 10h18m-12 5h6" /></>,
  reports: <><path d="M3 4v16h18M8 15v-3m5 3V8m5 7V5" /><circle cx="8" cy="8" r="1" /></>,
  inbox: <><rect x="3" y="5" width="18" height="14" rx="3" /><path d="m4 7 8 6 8-6" /></>,
  lock: <><rect x="5" y="10" width="14" height="11" rx="3" /><path d="M8 10V7a4 4 0 0 1 8 0v3m-4 4v3" /></>,
  check: <path d="m5 12 4 4L19 6" />,
};

export function WebsiteIcon({ name, ...props }: SVGProps<SVGSVGElement> & { name: keyof typeof paths }) {
  return (
    <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" {...props}>
      {paths[name]}
    </svg>
  );
}
