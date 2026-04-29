import { Footer } from "@/components/Footer";
import { Hero } from "@/components/Hero";
import { HowItWorks } from "@/components/HowItWorks";
import { Ingredients } from "@/components/Ingredients";
import { Nav } from "@/components/Nav";
import { Stats } from "@/components/Stats";
import { Waitlist } from "@/components/Waitlist";

export default function Home() {
  return (
    <main className="min-h-screen bg-navy text-ivory">
      <Nav />
      <Hero />
      <Stats />
      <HowItWorks />
      <Ingredients />
      <Waitlist />
      <Footer />
    </main>
  );
}
