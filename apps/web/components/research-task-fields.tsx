"use client";

import { useState } from "react";

export type TaskTemplate = {
  key: string;
  name: string;
  description: string;
  required_inputs: string[];
  optional_inputs: string[];
  required_output_fields: string[];
  recommended_tools: string[];
  guidance: string | null;
};

const INPUT_LABELS: Record<string, { label: string; placeholder: string }> = {
  ticker: { label: "Ticker", placeholder: "ACME" },
  quarter: { label: "Quarter", placeholder: "Q4 2023" },
  period: { label: "Period", placeholder: "FY2023" },
  hypothesis: { label: "Hypothesis", placeholder: "Software mix shift is durable" },
  focus: { label: "Focus", placeholder: "Margin structure" },
  universe: { label: "Universe", placeholder: "ACME, BLTA, CRUX" },
  peer_tickers: { label: "Peer tickers", placeholder: "BLTA, CRUX" },
};

/**
 * The template decides what the task needs, so the form follows it: a template builds its
 * own question from its inputs, and only a custom task has to be written out longhand.
 * Marking the genuinely required fields `required` means the browser stops an incomplete
 * submission at the field rather than the server rejecting it after the fact.
 */
export function ResearchTaskFields({ templates }: { templates: TaskTemplate[] }) {
  const [templateKey, setTemplateKey] = useState("custom");
  const template = templates.find((entry) => entry.key === templateKey);
  const isCustom = templateKey === "custom";

  // `question` is an input of the custom template, but it already has its own textarea.
  const inputs = template
    ? [
        ...template.required_inputs.map((name) => ({ name, required: true })),
        ...template.optional_inputs.map((name) => ({ name, required: false })),
      ].filter((input) => input.name !== "question")
    : [];

  return (
    <>
      <div>
        <label className="field-label" htmlFor="template">
          Task template
        </label>
        <select
          id="template"
          name="template"
          className="field-input"
          value={templateKey}
          onChange={(event) => setTemplateKey(event.target.value)}
        >
          {templates.map((entry) => (
            <option key={entry.key} value={entry.key}>
              {entry.name}
            </option>
          ))}
        </select>
        {template ? <p className="field-hint">{template.description}</p> : null}
      </div>

      <div>
        <label className="field-label" htmlFor="question">
          Question{isCustom ? "" : " (optional override)"}
        </label>
        <textarea
          id="question"
          name="question"
          rows={4}
          required={isCustom}
          className="field-input"
          placeholder="What was ACME Technologies' FY2023 revenue growth, and what drove it?"
        />
        <p className="field-hint">
          {isCustom
            ? "A custom task has no template question, so this is what the agent is asked."
            : "Leave blank to use the template's question, built from the inputs below."}
        </p>
      </div>

      {inputs.length > 0 ? (
        <div className="grid grid-cols-2 gap-3">
          {inputs.map(({ name, required }) => {
            const meta = INPUT_LABELS[name] ?? { label: name.replace(/_/g, " "), placeholder: "" };
            return (
              <div key={name}>
                <label className="field-label" htmlFor={name}>
                  {meta.label}
                  {required ? " *" : ""}
                </label>
                <input
                  id={name}
                  name={name}
                  required={required}
                  className="field-input"
                  placeholder={meta.placeholder}
                />
              </div>
            );
          })}
        </div>
      ) : null}

      {template && template.required_output_fields.length > 0 ? (
        <p className="field-hint">
          The answer must cover: {template.required_output_fields.join(", ").replace(/_/g, " ")}.
          Missing fields are reported as an instruction-adherence failure.
        </p>
      ) : null}
    </>
  );
}
