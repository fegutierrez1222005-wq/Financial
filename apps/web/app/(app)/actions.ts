"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { ApiRequestError, apiFetch } from "@/lib/api";
import type { Agent, Backtest, Evaluation, ResearchRun } from "@/lib/types";

export type ActionState = { error: string | null; message?: string | null };

/** Turn an API error into something safe and useful to show a user. */
function describe(error: unknown, fallback: string): ActionState {
  if (error instanceof ApiRequestError) {
    const fields = error.error.details?.fields as Array<{ field: string; message: string }> | undefined;
    if (fields?.length) {
      return {
        error: fields.map((field) => `${field.field}: ${field.message}`).join("; "),
        message: null,
      };
    }
    return { error: error.error.message, message: null };
  }
  return { error: fallback, message: null };
}

function list(value: FormDataEntryValue | null): string[] {
  return String(value ?? "")
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
}

// ------------------------------------------------------------------------- agents

export async function createAgent(_state: ActionState, formData: FormData): Promise<ActionState> {
  const tools = formData.getAll("tools").map(String);
  const body = {
    name: String(formData.get("name") ?? "").trim(),
    description: String(formData.get("description") ?? "").trim() || null,
    instructions: String(formData.get("instructions") ?? "").trim() || null,
    model: String(formData.get("model") ?? "") || null,
    temperature: Number(formData.get("temperature") ?? 0.2),
    max_steps: Number(formData.get("max_steps") ?? 8),
    output_format: String(formData.get("output_format") ?? "markdown"),
    tools,
    evaluation_suite_keys: list(formData.get("evaluation_suite_keys")),
    change_note: String(formData.get("change_note") ?? "").trim() || null,
  };
  if (!body.name) return { error: "Give the agent a name.", message: null };

  let agent: Agent;
  try {
    agent = await apiFetch<Agent>("/agents", { method: "POST", body });
  } catch (error) {
    return describe(error, "The agent could not be created.");
  }
  revalidatePath("/agents");
  redirect(`/agents/${agent.id}`);
}

export async function publishAgentVersion(
  _state: ActionState,
  formData: FormData,
): Promise<ActionState> {
  const agentId = String(formData.get("agent_id") ?? "");
  const body = {
    name: String(formData.get("name") ?? "").trim(),
    description: String(formData.get("description") ?? "").trim() || null,
    instructions: String(formData.get("instructions") ?? "").trim() || null,
    model: String(formData.get("model") ?? "") || null,
    temperature: Number(formData.get("temperature") ?? 0.2),
    max_steps: Number(formData.get("max_steps") ?? 8),
    output_format: String(formData.get("output_format") ?? "markdown"),
    tools: formData.getAll("tools").map(String),
    evaluation_suite_keys: list(formData.get("evaluation_suite_keys")),
    change_note: String(formData.get("change_note") ?? "").trim() || null,
  };
  try {
    await apiFetch(`/agents/${agentId}/versions`, { method: "POST", body });
  } catch (error) {
    return describe(error, "The new version could not be published.");
  }
  revalidatePath(`/agents/${agentId}`);
  return { error: null, message: "Published a new version. Previous versions remain available." };
}

// ----------------------------------------------------------------------- research

export async function startResearchRun(
  _state: ActionState,
  formData: FormData,
): Promise<ActionState> {
  const cutoff = String(formData.get("information_cutoff") ?? "").trim();

  // The template decides which inputs exist, so everything that is not a field of the run
  // itself is forwarded as a task input rather than matched against a hard-coded list.
  const RUN_FIELDS = new Set([
    "agent_id",
    "model_override",
    "template",
    "question",
    "information_cutoff",
    "evaluation_suite_key",
  ]);
  const inputs: Record<string, string> = {};
  for (const [key, raw] of formData.entries()) {
    if (RUN_FIELDS.has(key) || typeof raw !== "string") continue;
    const value = raw.trim();
    if (value) inputs[key] = value;
  }

  const body = {
    agent_id: String(formData.get("agent_id") ?? ""),
    model_override: String(formData.get("model_override") ?? "") || null,
    run_now: true,
    task: {
      template: String(formData.get("template") ?? "custom"),
      question: String(formData.get("question") ?? "").trim() || null,
      inputs,
      information_cutoff: cutoff ? new Date(`${cutoff}T23:59:59Z`).toISOString() : null,
      evaluation_suite_key: String(formData.get("evaluation_suite_key") ?? "") || null,
    },
  };
  if (!body.agent_id) return { error: "Choose an agent.", message: null };
  if (!body.task.question && body.task.template === "custom") {
    return { error: "Enter a research question.", message: null };
  }

  let run: ResearchRun;
  try {
    run = await apiFetch<ResearchRun>("/research/runs", { method: "POST", body });
  } catch (error) {
    return describe(error, "The run could not be started.");
  }
  revalidatePath("/research");
  redirect(`/research/runs/${run.id}`);
}

export async function reproduceRun(formData: FormData): Promise<void> {
  const runId = String(formData.get("run_id") ?? "");
  const repeat = await apiFetch<ResearchRun>(`/research/runs/${runId}/reproduce`, {
    method: "POST",
  });
  redirect(`/research/runs/${repeat.id}`);
}

export async function runDebate(formData: FormData): Promise<void> {
  const runId = String(formData.get("run_id") ?? "");
  await apiFetch(`/research/runs/${runId}/debate`, {
    method: "POST",
    body: { roles: ["bull", "bear", "skeptic", "judge"] },
  });
  revalidatePath(`/research/runs/${runId}`);
}

// --------------------------------------------------------------------- evaluation

export async function evaluateRun(formData: FormData): Promise<void> {
  const runId = String(formData.get("run_id") ?? "");
  const evaluation = await apiFetch<Evaluation>("/evaluations/runs", {
    method: "POST",
    body: { run_id: runId },
  });
  redirect(`/evaluations/${evaluation.id}`);
}

export async function runSuite(_state: ActionState, formData: FormData): Promise<ActionState> {
  const body = {
    suite_key: String(formData.get("suite_key") ?? ""),
    agent_id: String(formData.get("agent_id") ?? ""),
    max_cases: formData.get("max_cases") ? Number(formData.get("max_cases")) : null,
  };
  if (!body.suite_key || !body.agent_id) {
    return { error: "Choose a suite and an agent.", message: null };
  }

  let evaluation: Evaluation;
  try {
    evaluation = await apiFetch<Evaluation>("/evaluations/suites/run", { method: "POST", body });
  } catch (error) {
    return describe(error, "The suite could not be run.");
  }
  revalidatePath("/evaluations");
  redirect(`/evaluations/${evaluation.id}`);
}

// -------------------------------------------------------------------- backtesting

export async function createBacktest(
  _state: ActionState,
  formData: FormData,
): Promise<ActionState> {
  const body = {
    name: String(formData.get("name") ?? "").trim(),
    universe: list(formData.get("universe")).map((symbol) => symbol.toUpperCase()),
    start_date: String(formData.get("start_date") ?? ""),
    end_date: String(formData.get("end_date") ?? ""),
    lookback_days: Number(formData.get("lookback_days") ?? 126),
    top_n: Number(formData.get("top_n") ?? 3),
    rebalance_frequency: String(formData.get("rebalance_frequency") ?? "monthly"),
    transaction_cost_bps: Number(formData.get("transaction_cost_bps") ?? 10),
    slippage_bps: Number(formData.get("slippage_bps") ?? 5),
    signal_lag_days: Number(formData.get("signal_lag_days") ?? 1),
    initial_capital: Number(formData.get("initial_capital") ?? 10_000_000),
  };
  if (!body.name || body.universe.length === 0) {
    return { error: "Give the backtest a name and at least one symbol.", message: null };
  }

  let backtest: Backtest;
  try {
    backtest = await apiFetch<Backtest>("/backtests", { method: "POST", body });
  } catch (error) {
    return describe(error, "The backtest could not be created.");
  }
  revalidatePath("/backtests");
  redirect(`/backtests/${backtest.id}`);
}

export async function runBacktest(formData: FormData): Promise<void> {
  const backtestId = String(formData.get("backtest_id") ?? "");
  await apiFetch(`/backtests/${backtestId}/run`, { method: "POST" });
  revalidatePath(`/backtests/${backtestId}`);
  // A backtest has no status of its own — its splits appear only once the job finishes.
  // The flag tells the page a result is expected, so it can poll instead of showing an
  // empty "not run yet" state that a worker is in the middle of filling in.
  redirect(`/backtests/${backtestId}?awaiting=1`);
}

// -------------------------------------------------------------------- experiments

export async function createExperiment(
  _state: ActionState,
  formData: FormData,
): Promise<ActionState> {
  const armA = String(formData.get("arm_a_agent_id") ?? "");
  const armB = String(formData.get("arm_b_agent_id") ?? "");
  if (!armA || !armB) return { error: "Choose an agent for both arms.", message: null };

  const body = {
    name: String(formData.get("name") ?? "").trim(),
    variable: String(formData.get("variable") ?? "agent_version"),
    suite_key: String(formData.get("suite_key") ?? ""),
    hypothesis: String(formData.get("hypothesis") ?? "").trim() || null,
    max_cases: formData.get("max_cases") ? Number(formData.get("max_cases")) : null,
    arms: [
      {
        label: String(formData.get("arm_a_label") ?? "A"),
        agent_id: armA,
        model: String(formData.get("arm_a_model") ?? "") || null,
      },
      {
        label: String(formData.get("arm_b_label") ?? "B"),
        agent_id: armB,
        model: String(formData.get("arm_b_model") ?? "") || null,
      },
    ],
  };
  if (!body.name || !body.suite_key) {
    return { error: "Give the experiment a name and choose a suite.", message: null };
  }

  let experiment: { id: string };
  try {
    experiment = await apiFetch<{ id: string }>("/experiments", { method: "POST", body });
  } catch (error) {
    return describe(error, "The experiment could not be created.");
  }
  revalidatePath("/experiments");
  redirect(`/experiments/${experiment.id}`);
}

export async function runExperiment(formData: FormData): Promise<void> {
  const experimentId = String(formData.get("experiment_id") ?? "");
  await apiFetch(`/experiments/${experimentId}/run`, { method: "POST" });
  revalidatePath(`/experiments/${experimentId}`);
}

// --------------------------------------------------------------------------- data

export async function uploadDocument(
  _state: ActionState,
  formData: FormData,
): Promise<ActionState> {
  const file = formData.get("file");
  if (!(file instanceof File) || file.size === 0) {
    return { error: "Choose a file to upload.", message: null };
  }

  const payload = new FormData();
  payload.set("file", file);
  for (const key of ["title", "source_label", "document_type", "ticker", "publication_timestamp"]) {
    const value = String(formData.get(key) ?? "").trim();
    if (value) {
      payload.set(key, key === "publication_timestamp" ? new Date(value).toISOString() : value);
    }
  }

  try {
    await apiFetch("/documents", { method: "POST", formData: payload });
  } catch (error) {
    return describe(error, "The document could not be indexed.");
  }
  revalidatePath("/data");
  return {
    error: null,
    message:
      "Document indexed. Without a publication date it will be excluded from any run that " +
      "carries an information cutoff.",
  };
}

export async function deleteDocument(formData: FormData): Promise<void> {
  const documentId = String(formData.get("document_id") ?? "");
  await apiFetch(`/documents/${documentId}`, { method: "DELETE" });
  revalidatePath("/data");
}

export async function seedDemoWorkspace(): Promise<void> {
  await apiFetch("/workspaces/demo", { method: "POST" });
  revalidatePath("/dashboard");
  redirect("/dashboard");
}
