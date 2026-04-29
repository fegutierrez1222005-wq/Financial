import { NextResponse } from "next/server";

export const runtime = "nodejs";

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export async function POST(request: Request) {
  let payload: { email?: unknown } = {};
  try {
    payload = (await request.json()) as { email?: unknown };
  } catch {
    return NextResponse.json(
      { error: "Invalid request body." },
      { status: 400 }
    );
  }

  const email =
    typeof payload.email === "string" ? payload.email.trim().toLowerCase() : "";

  if (!email || !EMAIL_REGEX.test(email)) {
    return NextResponse.json(
      { error: "Enter a valid email address." },
      { status: 400 }
    );
  }

  const apiKey = process.env.RESEND_API_KEY;

  // When RESEND_API_KEY is missing, we still accept the signup so the
  // pre-launch site works in local/dev environments. Set the env var in
  // Vercel to enable real email delivery.
  if (!apiKey) {
    if (process.env.NODE_ENV !== "production") {
      console.info("[zibs] waitlist signup (no Resend key set):", email);
    }
    return NextResponse.json({ ok: true, delivered: false });
  }

  try {
    const { Resend } = await import("resend");
    const resend = new Resend(apiKey);

    const fromAddress =
      process.env.WAITLIST_FROM_EMAIL ?? "Zibs <waitlist@zibs.com>";
    const notifyAddress = process.env.WAITLIST_NOTIFY_EMAIL ?? email;

    await resend.emails.send({
      from: fromAddress,
      to: [notifyAddress],
      replyTo: email,
      subject: "New Zibs waitlist signup",
      text: `New waitlist signup: ${email}`,
    });

    return NextResponse.json({ ok: true, delivered: true });
  } catch (error) {
    console.error("[zibs] waitlist send failure", error);
    return NextResponse.json(
      { error: "Could not add you to the list. Try again." },
      { status: 500 }
    );
  }
}
