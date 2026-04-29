import { CartDrawer } from "@/components/CartDrawer";
import { Footer } from "@/components/Footer";
import { Hero } from "@/components/Hero";
import { HowItWorks } from "@/components/HowItWorks";
import { Ingredients } from "@/components/Ingredients";
import { Nav } from "@/components/Nav";
import { Reserve } from "@/components/Reserve";
import { Stats } from "@/components/Stats";

export default function Home() {
  return (
    <main className="min-h-screen bg-navy text-ivory">
      <Nav />
      <Hero />
      <Stats />
      <HowItWorks />
      <Ingredients />
      <Reserve />
      <Footer />
      <CartDrawer />
    </main>
  );
}
