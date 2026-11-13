import type { EmploymentType, JobDetail, LocationTier, RoleCategory, SeniorityBand } from "../types";

/*
  Seed data for mock mode. Every company and posting here is invented.
  Each seed carries the few fields that differ; `toDetail` fills in the
  contract-shaped record (description text, apply URL, preview, ...).
*/

interface JobSeed {
  id: string;
  title: string;
  company: string;
  location: string | null;
  tier: LocationTier;
  level: SeniorityBand;
  category: RoleCategory;
  type?: EmploymentType;
  minYears: number;
  skills: string[];
  comp: string | null;
  daysAgo: number;
  about: string;
  does: string[];
  wants: string[];
}

const SEEDS: JobSeed[] = [
  {
    id: "job-lumenfold-backend",
    title: "Senior Backend Engineer, Ledger",
    company: "Lumenfold",
    location: "Remote (EU / UK)",
    tier: "remote",
    level: "senior",
    category: "software_engineering",
    minYears: 5,
    skills: ["Python", "PostgreSQL", "AWS", "Event-driven design", "Kafka"],
    comp: "EUR 95k - 125k",
    daysAgo: 2,
    about: "Lumenfold builds the double-entry ledger that small marketplaces use to move money without a finance team.",
    does: ["Own the posting pipeline that turns payment events into immutable ledger entries", "Design idempotent consumers on Kafka and keep end-to-end latency under 300 ms", "Mentor two mid-level engineers and lead the quarterly reliability review"],
    wants: ["5+ years building backend services in Python or a similar language", "Deep PostgreSQL knowledge: locking, indexes, query plans", "Comfort with AWS and infrastructure as code"],
  },
  {
    id: "job-quillbase-platform",
    title: "Backend Engineer, Platform",
    company: "Quillbase",
    location: "Remote (Americas)",
    tier: "remote",
    level: "mid",
    category: "software_engineering",
    minYears: 3,
    skills: ["Go", "Python", "Kubernetes", "PostgreSQL", "gRPC"],
    comp: "USD 120k - 150k",
    daysAgo: 1,
    about: "Quillbase is a collaborative writing tool; the platform team keeps documents fast, synced and never lost.",
    does: ["Build the sync service that merges concurrent edits", "Ship gRPC APIs consumed by web, mobile and desktop clients", "Improve on-call tooling and cut alert noise"],
    wants: ["3+ years of backend experience", "Production Kubernetes experience", "Clear written communication, we are fully distributed"],
  },
  {
    id: "job-tessellate-ml",
    title: "Machine Learning Engineer, Ranking",
    company: "Tessellate Labs",
    location: "Bengaluru, India",
    tier: "hybrid",
    level: "mid",
    category: "data_and_analytics",
    minYears: 3,
    skills: ["Python", "PyTorch", "Search ranking", "Feature stores", "SQL"],
    comp: "INR 38L - 55L",
    daysAgo: 4,
    about: "Tessellate Labs builds discovery software for online catalogs and needs ranking models that earn their keep.",
    does: ["Train and evaluate learning-to-rank models on click and purchase data", "Own offline metrics and an A/B testing pipeline", "Partner with search engineers to ship models behind a feature flag"],
    wants: ["3+ years applying ML in production", "Strong Python and SQL", "Experience with ranking, recommendations or retrieval"],
  },
  {
    id: "job-brightloom-frontend",
    title: "Frontend Engineer",
    company: "Brightloom",
    location: "London, UK",
    tier: "hybrid",
    level: "mid",
    category: "software_engineering",
    minYears: 3,
    skills: ["TypeScript", "React", "Next.js", "Accessibility", "Tailwind CSS"],
    comp: "GBP 70k - 90k",
    daysAgo: 3,
    about: "Brightloom makes scheduling software for independent clinics, with an interface that has to work for tired people on old tablets.",
    does: ["Build accessible, fast interfaces in React and Next.js", "Own the design system's component library", "Run usability sessions with clinic staff"],
    wants: ["3+ years shipping production React", "Strong grasp of web accessibility", "An eye for detail and restraint"],
  },
  {
    id: "job-kestrel-data",
    title: "Data Analyst, Growth",
    company: "Kestrel Ledger",
    location: "Remote (India)",
    tier: "remote",
    level: "entry",
    category: "data_and_analytics",
    minYears: 1,
    skills: ["SQL", "Python", "dbt", "Looker", "Experimentation"],
    comp: "INR 14L - 20L",
    daysAgo: 5,
    about: "Kestrel Ledger offers bookkeeping software for freelancers; growth analytics decides which experiments ship.",
    does: ["Write clean SQL and dbt models for the growth funnel", "Analyze experiments and write up recommendations", "Build dashboards the team actually opens"],
    wants: ["1+ years in an analytics role or a strong internship", "Solid SQL; Python is a plus", "Curiosity about why numbers move"],
  },
  {
    id: "job-fernwood-pm",
    title: "Product Manager, Payments",
    company: "Fernwood Pay",
    location: "Singapore",
    tier: "onsite",
    level: "senior",
    category: "product_and_design",
    minYears: 5,
    skills: ["Roadmapping", "Payments", "SQL", "Stakeholder management", "Experimentation"],
    comp: "SGD 140k - 175k",
    daysAgo: 6,
    about: "Fernwood Pay processes card and bank payments for regional merchants. The payments PM owns checkout success.",
    does: ["Own the roadmap for checkout and payment-method coverage", "Work with compliance on new market launches", "Define the metrics that tell us when checkout is healthy"],
    wants: ["5+ years of product management", "Experience with payments or marketplaces", "Comfortable with SQL and experiments"],
  },
  {
    id: "job-halcyon-devops",
    title: "Site Reliability Engineer",
    company: "Halcyon Freight",
    location: "Remote",
    tier: "remote",
    level: "senior",
    category: "software_engineering",
    minYears: 5,
    skills: ["Terraform", "AWS", "Observability", "Python", "Incident response"],
    comp: "USD 135k - 165k",
    daysAgo: 7,
    about: "Halcyon Freight tracks containers across 40 ports; downtime means trucks idling at gates.",
    does: ["Run our AWS footprint with Terraform and keep it boring", "Build SLOs, dashboards and alerts people trust", "Lead blameless post-incident reviews"],
    wants: ["5+ years in SRE, DevOps or platform roles", "Fluent in Terraform and AWS", "Calm under pressure"],
  },
  {
    id: "job-marrow-intern",
    title: "Software Engineering Intern",
    company: "Marrowlytics",
    location: "Pune, India",
    tier: "onsite",
    level: "intern",
    category: "software_engineering",
    type: "internship",
    minYears: 0,
    skills: ["Python", "REST APIs", "Git", "SQL"],
    comp: "INR 40k / month",
    daysAgo: 2,
    about: "Marrowlytics turns hospital operations data into dashboards. Interns ship real features from week two.",
    does: ["Build and test REST endpoints in Python", "Pair with a mentor on code review each week", "Present your project to the whole company in month three"],
    wants: ["Final-year student or recent graduate", "Comfort with Python and Git", "Eagerness to learn"],
  },
  {
    id: "job-orchard-design",
    title: "Product Designer",
    company: "Cobalt Orchard",
    location: "Berlin, Germany",
    tier: "hybrid",
    level: "mid",
    category: "product_and_design",
    minYears: 3,
    skills: ["Figma", "Design systems", "User research", "Prototyping"],
    comp: "EUR 65k - 80k",
    daysAgo: 8,
    about: "Cobalt Orchard builds inventory tools for independent grocers. Design is two people and growing.",
    does: ["Design end-to-end flows from research through handoff", "Extend our design system", "Run weekly customer calls"],
    wants: ["3+ years of product design", "A portfolio showing real shipped work", "Comfortable with ambiguity"],
  },
  {
    id: "job-driftwood-fullstack",
    title: "Full-Stack Engineer",
    company: "Driftwood Systems",
    location: "Remote (Worldwide)",
    tier: "remote",
    level: "mid",
    category: "software_engineering",
    minYears: 2,
    skills: ["TypeScript", "Node.js", "React", "PostgreSQL", "AWS"],
    comp: "USD 90k - 120k",
    daysAgo: 1,
    about: "Driftwood Systems builds internal-tool software for logistics teams; a small team with a lot of ownership.",
    does: ["Ship features across the React frontend and Node.js services", "Model data in PostgreSQL and keep migrations safe", "Talk with customers about what to build next"],
    wants: ["2+ years of full-stack experience", "TypeScript everywhere", "Self-directed and collaborative"],
  },
  {
    id: "job-paperkite-marketing",
    title: "Growth Marketing Manager",
    company: "Paperkite",
    location: "Mumbai, India",
    tier: "hybrid",
    level: "mid",
    category: "marketing_and_growth",
    minYears: 4,
    skills: ["SEO", "Lifecycle email", "Analytics", "Paid acquisition"],
    comp: "INR 24L - 32L",
    daysAgo: 9,
    about: "Paperkite sells stationery subscriptions; growth marketing owns acquisition and retention end to end.",
    does: ["Plan and run acquisition experiments across paid and organic", "Own lifecycle email and win-back flows", "Report CAC and payback every month"],
    wants: ["4+ years in growth or performance marketing", "Analytical and numerate", "Strong written voice"],
  },
  {
    id: "job-nimbus-data-eng",
    title: "Data Engineer",
    company: "Nimbus Harbor",
    location: "Hyderabad, India",
    tier: "hybrid",
    level: "mid",
    category: "data_and_analytics",
    minYears: 3,
    skills: ["Python", "SQL", "Airflow", "Spark", "AWS"],
    comp: "INR 30L - 42L",
    daysAgo: 4,
    about: "Nimbus Harbor aggregates shipping-weather data for insurers, which means a lot of messy upstream sources.",
    does: ["Build reliable batch and streaming pipelines", "Add data-quality checks and lineage", "Keep the warehouse cost curve flat"],
    wants: ["3+ years in data engineering", "Strong SQL and Python", "Experience with Airflow or similar"],
  },
];

const daysAgoIso = (d: number) => new Date(Date.now() - d * 86_400_000).toISOString();
const bullets = (items: string[]) => items.map((i) => `- ${i}`).join("\n");

function toDetail(seed: JobSeed): JobDetail {
  const description = [
    seed.about,
    `## What you will do\n${bullets(seed.does)}`,
    `## What we are looking for\n${bullets(seed.wants)}`,
    `## Tools you will use\n${bullets(seed.skills)}`,
  ].join("\n\n");
  return {
    job_id: seed.id,
    title: seed.title,
    company: seed.company,
    location_text: seed.location,
    location_tier: seed.tier,
    seniority_band: seed.level,
    role_category: seed.category,
    skills: seed.skills,
    description_preview: seed.about,
    compensation_text: seed.comp,
    apply_url: `https://careers.example.com/${seed.id}`,
    match_score: 70,
    match_reasons: [],
    posted_at: daysAgoIso(seed.daysAgo),
    is_saved: false,
    description,
    employment_type: seed.type ?? "full_time",
    min_years_experience: seed.minYears,
  };
}

export const JOBS: JobDetail[] = SEEDS.map(toDetail);
