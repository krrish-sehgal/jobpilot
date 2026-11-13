import type { ResumeSections } from "../types";

/** The parsed resume every mock upload resolves to. Fixed sample content for offline mode. */
export const SAMPLE_SECTIONS: ResumeSections = {
  contact: {
    name: "Riya Calloway",
    email: "riya.calloway@example.com",
    phone: "+91 98000 00000",
    location: "Pune, India",
    links: ["github.com/riyacalloway", "linkedin.com/in/riyacalloway"],
  },
  summary:
    "Backend engineer with three years of experience building web services. Comfortable across the stack and keen on reliable, well-tested systems.",
  experience: [
    {
      id: "exp-1",
      company: "Stackwell Software",
      title: "Software Engineer",
      start: "2023-07",
      end: null,
      bullets: [
        { id: "b-1", text: "Built REST APIs for the billing module used by 40 enterprise customers." },
        { id: "b-2", text: "Wrote database queries and improved slow endpoints, reducing page load time." },
        { id: "b-3", text: "Worked with the team to deploy services and fix production issues." },
      ],
    },
    {
      id: "exp-2",
      company: "Gridnote Studio",
      title: "Software Engineering Intern",
      start: "2022-12",
      end: "2023-06",
      bullets: [
        { id: "b-4", text: "Developed internal tools in Python that automated weekly reporting." },
        { id: "b-5", text: "Added unit tests and helped move the project to a CI pipeline." },
      ],
    },
  ],
  education: [
    {
      id: "edu-1",
      institution: "Western Ridge Institute of Technology",
      degree: "B.Tech, Computer Science",
      start: "2019",
      end: "2023",
      score: "8.4 CGPA",
    },
  ],
  projects: [
    {
      id: "proj-1",
      name: "Pantry Planner",
      tech: ["Python", "SQLite", "Flask"],
      bullets: [{ id: "b-6", text: "Built a meal-planning web app used by 200 beta testers." }],
    },
  ],
  skills: ["Python", "SQL", "Flask", "PostgreSQL", "Git", "Docker", "REST APIs", "Linux"],
};
