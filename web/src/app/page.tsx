import { Hero } from "@/components/marketing/Hero";
import { Cta, Features, HowItWorks } from "@/components/marketing/Sections";
import { SiteFooter, SiteHeader } from "@/components/marketing/SiteHeader";

export default function LandingPage() {
  return (
    <>
      <SiteHeader />
      <main>
        <Hero />
        <HowItWorks />
        <Features />
        <Cta />
      </main>
      <SiteFooter />
    </>
  );
}
