import type { EmploymentType, LocationTier, RoleCategory, SeniorityBand } from "@/lib/api/types";

/** Display text for the contract's enum values. One place, so copy changes stay consistent. */
export const seniorityLabel: Record<SeniorityBand, string> = {
  intern: "Intern", entry: "Entry level", mid: "Mid level", senior: "Senior", leadership: "Leadership",
};

export const tierLabel: Record<LocationTier, string> = {
  remote: "Remote", hybrid: "Hybrid", onsite: "On-site", unknown: "Location unspecified",
};

export const categoryLabel: Record<RoleCategory, string> = {
  software_engineering: "Software engineering",
  data_and_analytics: "Data and analytics",
  product_and_design: "Product and design",
  sales_and_business_dev: "Sales and business development",
  marketing_and_growth: "Marketing and growth",
  operations_and_support: "Operations and support",
  finance_and_legal: "Finance and legal",
  other: "Other",
};

export const employmentLabel: Record<EmploymentType, string> = {
  full_time: "Full time", part_time: "Part time", contract: "Contract", internship: "Internship",
};
