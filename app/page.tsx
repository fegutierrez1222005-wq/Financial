import { CartDrawer } from "@/components/CartDrawer";
import { FAQ } from "@/components/FAQ";
import { Flavors } from "@/components/Flavors";
import { Footer } from "@/components/Footer";
import { Hero } from "@/components/Hero";
import { HowItWorks } from "@/components/HowItWorks";
import { Ingredients } from "@/components/Ingredients";
import { Manifesto } from "@/components/Manifesto";
import { Mechanism } from "@/components/Mechanism";
import { Nav } from "@/components/Nav";
import { PartnerStrip } from "@/components/PartnerStrip";
import { Reserve } from "@/components/Reserve";
import { ScrollProgress } from "@/components/ScrollProgress";
import { Specs } from "@/components/Specs";
import { Stats } from "@/components/Stats";
import { Timeline } from "@/components/Timeline";

export default function Home() {
  return (
    <main className="min-h-screen bg-navy text-ivory">
      <ScrollProgress />
      <Nav />
      <Hero />
      <PartnerStrip />
      <Stats />
      <Mechanism />
      <Manifesto />
      <HowItWorks />
      <Ingredients />
      <Specs />
      <Timeline />
      <Flavors />
      <Reserve />
      <FAQ />
      <Footer />
      <CartDrawer />
    </main>
  );
}
