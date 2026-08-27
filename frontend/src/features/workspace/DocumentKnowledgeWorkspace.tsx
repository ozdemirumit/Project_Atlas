import { useMutation } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  ClipboardCheck,
  FileUp,
  Layers3,
  LockKeyhole,
  RotateCcw,
  Search,
  ShieldCheck,
} from "lucide-react";
import { type FormEvent, useState } from "react";

import { ApiRequestError } from "../../api/client";
import {
  chunkingProfileDigest,
  createDocumentKnowledgeDraft,
  fileToBase64,
  indexDocumentKnowledge,
  prepareDocumentKnowledgePublication,
  recordDocumentKnowledgeApproval,
  searchDocumentKnowledge,
  submitDocumentKnowledgeReview,
  type DocumentKnowledgeApproval,
  type DocumentKnowledgeApprovalDecision,
  type DocumentKnowledgeDraft,
  type DocumentKnowledgeIndexResult,
  type DocumentKnowledgePublicationPreparation,
  type DocumentKnowledgeReview,
  type DocumentKnowledgeReviewDecision,
  type DocumentKnowledgeSearchResult,
} from "../../api/documentKnowledge";
import "./DocumentKnowledgeWorkspace.css";

const STABLE_ID = /^[a-z][a-z0-9_.:-]{2,127}$/;

function errorDetail(error: unknown): string {
  if (error instanceof ApiRequestError) return error.message;
  return "This step could not be completed.";
}

function StageError({ error }: { error: unknown }) {
  if (!error) return null;
  return (
    <div className="document-knowledge-message error" role="alert">
      <AlertTriangle size={16} />
      <span>{errorDetail(error)}</span>
    </div>
  );
}

function IdentifierField({
  label,
  value,
  placeholder,
  onChange,
}: {
  label: string;
  value: string;
  placeholder: string;
  onChange: (value: string) => void;
}) {
  const valid = value.length === 0 || STABLE_ID.test(value);
  return (
    <label className="document-knowledge-field">
      {label}
      <input
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        aria-invalid={!valid}
      />
      {!valid && <small>Lowercase identifier, e.g. {placeholder}</small>}
    </label>
  );
}

function UploadStage({ onCreated }: { onCreated: (draft: DocumentKnowledgeDraft) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [draftDomain, setDraftDomain] = useState("domain.general-document");
  const [contentType, setContentType] = useState("");
  const [classification, setClassification] = useState("classification.internal");
  const [accessPolicyId, setAccessPolicyId] = useState("access-policy.default-internal");
  const [retentionPolicyId, setRetentionPolicyId] = useState("retention-policy.standard-12m");
  const [purpose, setPurpose] = useState("");

  const mutation = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error("A file is required.");
      const contentBase64 = await fileToBase64(file);
      return createDocumentKnowledgeDraft({
        contentBase64,
        title: title.trim(),
        draftDomain,
        contentType,
        classification,
        accessPolicyId,
        retentionPolicyId,
        purpose: purpose.trim(),
      });
    },
    onSuccess: onCreated,
  });

  const identifiersValid =
    STABLE_ID.test(draftDomain) &&
    STABLE_ID.test(classification) &&
    STABLE_ID.test(accessPolicyId) &&
    STABLE_ID.test(retentionPolicyId) &&
    /^[a-z]+\/[a-z0-9.+-]+$/.test(contentType);
  const valid =
    file !== null &&
    title.trim().length >= 1 &&
    title.trim().length <= 200 &&
    purpose.trim().length >= 20 &&
    purpose.trim().length <= 1000 &&
    identifiersValid;

  function submit(event: FormEvent) {
    event.preventDefault();
    if (valid && !mutation.isPending) mutation.mutate();
  }

  return (
    <form className="document-knowledge-stage" onSubmit={submit}>
      <h2>
        <FileUp size={18} /> Curate a document draft
      </h2>
      <p className="document-knowledge-stage-lede">
        Upload a PDF or Markdown document. Curation stores the raw content once, behind the
        protected-content boundary, and returns only a digest-bound draft.
      </p>
      <label className="document-knowledge-field">
        Document file
        <input
          type="file"
          accept=".pdf,.md,.markdown,.txt,application/pdf,text/markdown,text/plain"
          onChange={(event) => {
            const selected = event.target.files?.[0] ?? null;
            setFile(selected);
            if (selected && !title.trim()) setTitle(selected.name.replace(/\.[^.]+$/, ""));
            if (selected) {
              setContentType(
                selected.type ||
                  (selected.name.endsWith(".md") || selected.name.endsWith(".markdown")
                    ? "text/markdown"
                    : "application/octet-stream"),
              );
            }
          }}
        />
      </label>
      <label className="document-knowledge-field">
        Title
        <input
          value={title}
          maxLength={200}
          placeholder="Q3 storage capacity runbook"
          onChange={(event) => setTitle(event.target.value)}
        />
      </label>
      <label className="document-knowledge-field">
        Content type
        <input
          value={contentType}
          placeholder="application/pdf"
          onChange={(event) => setContentType(event.target.value)}
        />
      </label>
      <div className="document-knowledge-field-grid">
        <IdentifierField
          label="Draft domain"
          value={draftDomain}
          placeholder="domain.general-document"
          onChange={setDraftDomain}
        />
        <IdentifierField
          label="Classification"
          value={classification}
          placeholder="classification.internal"
          onChange={setClassification}
        />
        <IdentifierField
          label="Access policy"
          value={accessPolicyId}
          placeholder="access-policy.default-internal"
          onChange={setAccessPolicyId}
        />
        <IdentifierField
          label="Retention policy"
          value={retentionPolicyId}
          placeholder="retention-policy.standard-12m"
          onChange={setRetentionPolicyId}
        />
      </div>
      <label className="document-knowledge-field">
        Curation purpose (at least 20 characters)
        <textarea
          rows={3}
          minLength={20}
          maxLength={1000}
          value={purpose}
          placeholder="Explain why this document should become governed operational knowledge."
          onChange={(event) => setPurpose(event.target.value)}
        />
      </label>
      <div className="document-knowledge-boundary" role="note">
        <ShieldCheck size={17} />
        <span>
          Curation grants no publication, indexing, or infrastructure authority. Every later stage
          requires a separate reviewer and a separate approver.
        </span>
      </div>
      <StageError error={mutation.error} />
      <button className="document-knowledge-primary" type="submit" disabled={!valid || mutation.isPending}>
        {mutation.isPending ? "Curating…" : "Curate draft"} <ArrowRight size={15} />
      </button>
    </form>
  );
}

function ReviewStage({
  draft,
  onDecided,
}: {
  draft: DocumentKnowledgeDraft;
  onDecided: (review: DocumentKnowledgeReview) => void;
}) {
  const [decision, setDecision] = useState<DocumentKnowledgeReviewDecision>("passed");
  const [findingsText, setFindingsText] = useState("");
  const mutation = useMutation({
    mutationFn: () =>
      submitDocumentKnowledgeReview({
        draftId: draft.draft_id,
        decision,
        findings: findingsText
          .split("\n")
          .map((line) => line.trim())
          .filter((line) => line.length > 0),
      }),
    onSuccess: onDecided,
  });
  const findings = findingsText
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0);
  const valid = findings.length >= 1 && findings.length <= 20;

  function submit(event: FormEvent) {
    event.preventDefault();
    if (valid && !mutation.isPending) mutation.mutate();
  }

  return (
    <form className="document-knowledge-stage" onSubmit={submit}>
      <h2>
        <ClipboardCheck size={18} /> Review decision
      </h2>
      <p className="document-knowledge-stage-lede">
        Draft <strong>{draft.title}</strong> is awaiting review. The reviewer must be a different
        subject than the curator.
      </p>
      <label className="document-knowledge-field">
        Decision
        <select
          value={decision}
          onChange={(event) => setDecision(event.target.value as DocumentKnowledgeReviewDecision)}
        >
          <option value="passed">Passed</option>
          <option value="changes_required">Changes required</option>
          <option value="rejected">Rejected</option>
        </select>
      </label>
      <label className="document-knowledge-field">
        Findings (one per line)
        <textarea
          rows={3}
          value={findingsText}
          placeholder="Content is accurate and current as of this review."
          onChange={(event) => setFindingsText(event.target.value)}
        />
      </label>
      <StageError error={mutation.error} />
      {mutation.error instanceof ApiRequestError &&
        mutation.error.message.includes("separation_of_duties") && (
          <div className="document-knowledge-message warning" role="status">
            <ShieldCheck size={16} />
            <span>
              This platform session curated the draft, so it cannot also review it. Sign in as a
              different subject to continue this document, or use another draft to exercise
              review independently.
            </span>
          </div>
        )}
      <button className="document-knowledge-primary" type="submit" disabled={!valid || mutation.isPending}>
        {mutation.isPending ? "Submitting…" : "Submit review"} <ArrowRight size={15} />
      </button>
    </form>
  );
}

function ApprovalStage({
  review,
  onDecided,
}: {
  review: DocumentKnowledgeReview;
  onDecided: (approval: DocumentKnowledgeApproval) => void;
}) {
  const [decision, setDecision] = useState<DocumentKnowledgeApprovalDecision>("approved");
  const [rationale, setRationale] = useState("");
  const mutation = useMutation({
    mutationFn: () =>
      recordDocumentKnowledgeApproval({
        reviewId: review.review_id,
        decision,
        rationale: rationale.trim(),
      }),
    onSuccess: onDecided,
  });
  const valid = rationale.trim().length >= 20 && rationale.trim().length <= 1000;

  function submit(event: FormEvent) {
    event.preventDefault();
    if (valid && !mutation.isPending) mutation.mutate();
  }

  return (
    <form className="document-knowledge-stage" onSubmit={submit}>
      <h2>
        <LockKeyhole size={18} /> Final approval
      </h2>
      <p className="document-knowledge-stage-lede">
        The review passed. The approver must differ from both the curator and the reviewer.
      </p>
      <label className="document-knowledge-field">
        Decision
        <select
          value={decision}
          onChange={(event) => setDecision(event.target.value as DocumentKnowledgeApprovalDecision)}
        >
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
        </select>
      </label>
      <label className="document-knowledge-field">
        Rationale (at least 20 characters)
        <textarea
          rows={3}
          minLength={20}
          maxLength={1000}
          value={rationale}
          placeholder="Explain the basis for this final approval decision."
          onChange={(event) => setRationale(event.target.value)}
        />
      </label>
      <StageError error={mutation.error} />
      <button className="document-knowledge-primary" type="submit" disabled={!valid || mutation.isPending}>
        {mutation.isPending ? "Recording…" : "Record approval"} <ArrowRight size={15} />
      </button>
    </form>
  );
}

function PreparationStage({
  approval,
  onPrepared,
}: {
  approval: DocumentKnowledgeApproval;
  onPrepared: (preparation: DocumentKnowledgePublicationPreparation) => void;
}) {
  const [maxChunkCharacters, setMaxChunkCharacters] = useState(1200);
  const mutation = useMutation({
    mutationFn: async () => {
      const digest = await chunkingProfileDigest(
        `document-knowledge-chunking-profile.paragraph-bounded.v1:${maxChunkCharacters}`,
      );
      return prepareDocumentKnowledgePublication({
        approvalId: approval.approval_id,
        chunkingProfileDigest: digest,
      });
    },
    onSuccess: onPrepared,
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!mutation.isPending) mutation.mutate();
  }

  return (
    <form className="document-knowledge-stage" onSubmit={submit}>
      <h2>
        <Layers3 size={18} /> Publication preparation
      </h2>
      <p className="document-knowledge-stage-lede">
        Approval was granted. Preparation records the chunking profile that indexing will use.
      </p>
      <label className="document-knowledge-field">
        Maximum chunk size (characters)
        <input
          type="number"
          min={200}
          max={4000}
          value={maxChunkCharacters}
          onChange={(event) => setMaxChunkCharacters(Number(event.target.value))}
        />
      </label>
      <StageError error={mutation.error} />
      <button className="document-knowledge-primary" type="submit" disabled={mutation.isPending}>
        {mutation.isPending ? "Preparing…" : "Prepare publication"} <ArrowRight size={15} />
      </button>
    </form>
  );
}

function IndexStage({
  preparation,
  onIndexed,
}: {
  preparation: DocumentKnowledgePublicationPreparation;
  onIndexed: (result: DocumentKnowledgeIndexResult) => void;
}) {
  const mutation = useMutation({
    mutationFn: () => indexDocumentKnowledge({ preparationId: preparation.preparation_id }),
    onSuccess: onIndexed,
  });

  return (
    <div className="document-knowledge-stage">
      <h2>
        <CheckCircle2 size={18} /> Index for retrieval
      </h2>
      <p className="document-knowledge-stage-lede">
        Publication is prepared. Indexing chunks and embeds the approved content so it becomes
        searchable below.
      </p>
      <StageError error={mutation.error} />
      {mutation.error instanceof ApiRequestError &&
        mutation.error.message.includes("retrieval_unavailable") && (
          <div className="document-knowledge-message warning" role="status">
            <ShieldCheck size={16} />
            <span>Document retrieval is not enabled in this environment.</span>
          </div>
        )}
      <button
        className="document-knowledge-primary"
        type="button"
        disabled={mutation.isPending}
        onClick={() => mutation.mutate()}
      >
        {mutation.isPending ? "Indexing…" : "Index document"} <ArrowRight size={15} />
      </button>
    </div>
  );
}

function SearchPanel() {
  const [query, setQuery] = useState("");
  const mutation = useMutation({
    mutationFn: () => searchDocumentKnowledge({ query: query.trim(), topK: 5 }),
  });
  const valid = query.trim().length >= 3 && query.trim().length <= 4000;

  function submit(event: FormEvent) {
    event.preventDefault();
    if (valid && !mutation.isPending) mutation.mutate();
  }

  return (
    <section className="document-knowledge-search" aria-labelledby="document-knowledge-search-title">
      <h2 id="document-knowledge-search-title">
        <Search size={18} /> Search indexed documents
      </h2>
      <form onSubmit={submit}>
        <input
          aria-label="Search query"
          value={query}
          placeholder="Ask about anything indexed from an approved document"
          onChange={(event) => setQuery(event.target.value)}
        />
        <button type="submit" disabled={!valid || mutation.isPending}>
          {mutation.isPending ? "Searching…" : "Search"}
        </button>
      </form>
      <StageError error={mutation.error} />
      {mutation.data && mutation.data.length === 0 && (
        <p className="document-knowledge-search-empty">No indexed passages matched this query.</p>
      )}
      {mutation.data && mutation.data.length > 0 && (
        <ul className="document-knowledge-search-results">
          {mutation.data.map((result: DocumentKnowledgeSearchResult) => (
            <li key={result.chunk_id}>
              <div className="document-knowledge-search-result-heading">
                <span className="document-knowledge-search-score">
                  {(result.score * 100).toFixed(1)}%
                </span>
                <span>{result.knowledge_item_id}</span>
              </div>
              <p>{result.excerpt}</p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

type PipelineState = {
  draft: DocumentKnowledgeDraft | null;
  review: DocumentKnowledgeReview | null;
  approval: DocumentKnowledgeApproval | null;
  preparation: DocumentKnowledgePublicationPreparation | null;
  indexResult: DocumentKnowledgeIndexResult | null;
};

const EMPTY_PIPELINE: PipelineState = {
  draft: null,
  review: null,
  approval: null,
  preparation: null,
  indexResult: null,
};

export default function DocumentKnowledgeWorkspace() {
  const [pipeline, setPipeline] = useState<PipelineState>(EMPTY_PIPELINE);
  const { draft, review, approval, preparation, indexResult } = pipeline;

  return (
    <section className="document-knowledge-workspace" aria-labelledby="document-knowledge-title">
      <header className="document-knowledge-heading">
        <div>
          <p className="eyebrow">WORKSPACE</p>
          <h1 id="document-knowledge-title">Document knowledge</h1>
          <p>
            Curate, review, approve, and publish documents into governed retrieval knowledge. See
            ADR-184.
          </p>
        </div>
        {draft && (
          <button
            className="document-knowledge-restart"
            type="button"
            onClick={() => setPipeline(EMPTY_PIPELINE)}
          >
            <RotateCcw size={15} /> Start another document
          </button>
        )}
      </header>

      {!draft && <UploadStage onCreated={(created) => setPipeline({ ...EMPTY_PIPELINE, draft: created })} />}
      {draft && !review && (
        <ReviewStage draft={draft} onDecided={(decided) => setPipeline((state) => ({ ...state, review: decided }))} />
      )}
      {review && review.decision !== "passed" && !approval && (
        <div className="document-knowledge-message warning" role="status">
          <AlertTriangle size={16} />
          <span>
            This review did not pass ({review.decision}). Publication preparation is unavailable
            for this document.
          </span>
        </div>
      )}
      {review && review.decision === "passed" && !approval && (
        <ApprovalStage review={review} onDecided={(decided) => setPipeline((state) => ({ ...state, approval: decided }))} />
      )}
      {approval && approval.decision !== "approved" && !preparation && (
        <div className="document-knowledge-message warning" role="status">
          <AlertTriangle size={16} />
          <span>This document was not approved. Publication preparation is unavailable.</span>
        </div>
      )}
      {approval && approval.decision === "approved" && !preparation && (
        <PreparationStage
          approval={approval}
          onPrepared={(prepared) => setPipeline((state) => ({ ...state, preparation: prepared }))}
        />
      )}
      {preparation && !indexResult && (
        <IndexStage
          preparation={preparation}
          onIndexed={(result) => setPipeline((state) => ({ ...state, indexResult: result }))}
        />
      )}
      {indexResult && (
        <div className="document-knowledge-message success" role="status">
          <CheckCircle2 size={16} />
          <span>
            Indexed {indexResult.chunk_count} chunk{indexResult.chunk_count === 1 ? "" : "s"}. This
            document is now searchable below.
          </span>
        </div>
      )}

      <SearchPanel />
    </section>
  );
}
