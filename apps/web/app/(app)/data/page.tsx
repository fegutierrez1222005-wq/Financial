import type { Metadata } from "next";

import { ActionForm, SubmitButton } from "@/components/action-form";
import {
  Badge,
  EmptyState,
  Notice,
  PageHeader,
  Panel,
  StatusBadge,
} from "@/components/primitives";
import { deleteDocument, uploadDocument } from "@/app/(app)/actions";
import { apiFetchOrNull } from "@/lib/api";
import { formatBytes, formatDateTime } from "@/lib/format";
import type { FinDocument, ProviderStatus } from "@/lib/types";

export const metadata: Metadata = { title: "Data" };

export default async function DataPage() {
  const [documents, stats, providers] = await Promise.all([
    apiFetchOrNull<FinDocument[]>("/documents"),
    apiFetchOrNull<Record<string, number | string>>("/documents/stats"),
    apiFetchOrNull<ProviderStatus>("/providers/status"),
  ]);

  const missingDates = (documents ?? []).filter(
    (document) => !document.publication_timestamp,
  ).length;

  return (
    <>
      <PageHeader
        title="Data"
        subtitle="The corpus an agent may read, and the providers it may call. A document's publication date is what makes historical research honest."
      />

      {missingDates > 0 ? (
        <div className="mb-4">
          <Notice tone="caution">
            {missingDates} document(s) have no publication date. They are searchable, but they are
            excluded from every run that carries an information cutoff, because their provenance
            cannot be verified.
          </Notice>
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-[1fr_1.6fr]">
        <div className="space-y-4">
          <Panel title="Upload a document">
            <div className="p-4">
              <ActionForm action={uploadDocument} submitLabel="Index document" pendingLabel="Indexing…">
                <div className="space-y-4">
                  <div>
                    <label className="field-label" htmlFor="file">
                      File
                    </label>
                    <input
                      id="file"
                      name="file"
                      type="file"
                      required
                      accept=".pdf,.html,.htm,.txt,.md,.csv,.xlsx"
                      className="field-input file:mr-3 file:rounded file:border-0 file:bg-ink-700 file:px-2.5 file:py-1 file:text-2xs file:text-ink-200"
                    />
                    <p className="field-hint">PDF, HTML, TXT, MD, CSV or XLSX.</p>
                  </div>
                  <div>
                    <label className="field-label" htmlFor="publication_timestamp">
                      Publication date
                    </label>
                    <input
                      id="publication_timestamp"
                      name="publication_timestamp"
                      type="date"
                      className="field-input numeric"
                    />
                    <p className="field-hint">
                      When this document became public. Without it the document cannot be used in
                      any as-of-restricted run.
                    </p>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="field-label" htmlFor="ticker">
                        Ticker
                      </label>
                      <input id="ticker" name="ticker" className="field-input" />
                    </div>
                    <div>
                      <label className="field-label" htmlFor="document_type">
                        Type
                      </label>
                      <input
                        id="document_type"
                        name="document_type"
                        className="field-input"
                        placeholder="10-K"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="field-label" htmlFor="source_label">
                      Source label
                    </label>
                    <input
                      id="source_label"
                      name="source_label"
                      className="field-input"
                      placeholder="SEC EDGAR"
                    />
                  </div>
                </div>
              </ActionForm>
            </div>
          </Panel>

          <Panel title="Corpus">
            {stats ? (
              <dl className="divide-y divide-ink-800">
                {Object.entries(stats).map(([key, value]) => (
                  <div key={key} className="flex items-baseline justify-between px-4 py-2">
                    <dt className="text-2xs uppercase tracking-[0.1em] text-ink-400">
                      {key.replace(/_/g, " ")}
                    </dt>
                    <dd className="numeric text-sm">{String(value)}</dd>
                  </div>
                ))}
              </dl>
            ) : (
              <EmptyState title="No statistics" description="The corpus is empty." />
            )}
          </Panel>

          <Panel
            title="Providers"
            description="Availability only. Credentials are never returned by the API."
          >
            {providers ? (
              <>
                <ul className="divide-y divide-ink-800">
                  {providers.data_providers.map((provider) => (
                    <li
                      key={provider.key}
                      className="flex items-center justify-between gap-3 px-4 py-2.5"
                    >
                      <div>
                        <div className="text-sm text-ink-200">{provider.display_name}</div>
                        <div className="mt-0.5 text-2xs text-ink-500">
                          {provider.capabilities.join(", ")}
                        </div>
                      </div>
                      {provider.is_demo ? (
                        <Badge tone="mock">Demo</Badge>
                      ) : provider.status === "available" ? (
                        <Badge tone="positive">Available</Badge>
                      ) : (
                        <Badge tone="neutral">No credentials</Badge>
                      )}
                    </li>
                  ))}
                </ul>
                <div className="border-t border-ink-800 px-4 py-3">
                  <Notice tone="info">{providers.notice}</Notice>
                </div>
              </>
            ) : (
              <EmptyState title="Unavailable" description="Provider status could not be read." />
            )}
          </Panel>
        </div>

        <Panel title="Documents">
          {!documents || documents.length === 0 ? (
            <EmptyState
              title="No documents indexed"
              description="Upload a filing, transcript or memo. It is chunked, embedded and made searchable, and every chunk keeps its page number so a citation can be checked."
            />
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Document</th>
                  <th>Status</th>
                  <th>Published</th>
                  <th>Pages</th>
                  <th>Chunks</th>
                  <th>Size</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {documents.map((document) => (
                  <tr key={document.id}>
                    <td>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-ink-100">{document.title ?? document.filename}</span>
                        {document.is_demo ? <Badge tone="mock">Demo</Badge> : null}
                        {document.embedding_is_mock ? (
                          <Badge
                            tone="mock"
                            title="Indexed with the deterministic local embedding provider, not a trained embedding model."
                          >
                            Local embeddings
                          </Badge>
                        ) : null}
                      </div>
                      <div className="mt-0.5 text-2xs text-ink-500">
                        {document.ticker ? `${document.ticker} · ` : ""}
                        {document.document_type ?? document.extension}
                        {document.source_label ? ` · ${document.source_label}` : ""}
                      </div>
                      {document.error_message ? (
                        <div className="mt-1 text-2xs text-signal-negative">
                          {document.error_message}
                        </div>
                      ) : null}
                    </td>
                    <td>
                      <StatusBadge status={document.status} />
                    </td>
                    <td className="text-2xs">
                      {document.publication_timestamp ? (
                        <span className="text-ink-300">
                          {formatDateTime(document.publication_timestamp)}
                        </span>
                      ) : (
                        <span className="text-signal-caution">unknown</span>
                      )}
                    </td>
                    <td className="numeric">{document.page_count ?? "—"}</td>
                    <td className="numeric">{document.chunk_count}</td>
                    <td className="numeric text-2xs">{formatBytes(document.size_bytes)}</td>
                    <td>
                      <form action={deleteDocument}>
                        <input type="hidden" name="document_id" value={document.id} />
                        <SubmitButton label="Delete" pendingLabel="Deleting…" variant="danger" />
                      </form>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <div className="border-t border-ink-800 px-4 py-3">
            <Notice tone="info">
              Deleting a document removes it from every retrieval path immediately. The record is
              retained with a deletion timestamp so past runs keep their audit trail, but its text
              can no longer be returned as evidence.
            </Notice>
          </div>
        </Panel>
      </div>
    </>
  );
}
