import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BadgeCheck, Link2, RefreshCw, ShieldCheck, X } from "lucide-react";
import { useState, type FormEvent } from "react";

import {
  HITACHI_AUTHORIZATION_SECRET_REFERENCE,
  getBundledConnectionConfiguration,
  saveBundledConnectionConfiguration,
  testBundledConnectorConnection,
  type BundledConnectionConfiguration,
  type ConnectorConnectionTestResult,
} from "../../api/bundledConnectorConnections";
import type { ConnectorInstanceRecord } from "../../api/connectorInstances";

export function BundledConnectionDialog({
  configuration,
  instance,
  onCancel,
  onConfigured,
  onTested,
}: {
  configuration?: BundledConnectionConfiguration | null;
  instance: ConnectorInstanceRecord;
  onCancel: () => void;
  onConfigured: (configuration: BundledConnectionConfiguration) => void;
  onTested?: (result: ConnectorConnectionTestResult) => void;
}) {
  const queryClient = useQueryClient();
  const queryKey = ["bundled-connection-configuration", instance.instance_id] as const;
  const configurationQuery = useQuery({
    queryKey,
    queryFn: () => getBundledConnectionConfiguration(instance.instance_id),
    initialData: configuration,
    retry: false,
  });
  const current = configurationQuery.data;
  const [hostnameOverride, setHostnameOverride] = useState("");
  const [portOverride, setPortOverride] = useState<number | null>(null);
  const hostname = hostnameOverride || current?.hostname || "";
  const port = portOverride ?? current?.port ?? 23450;

  const saveMutation = useMutation({
    mutationFn: () => saveBundledConnectionConfiguration({
      instanceId: instance.instance_id,
      hostname,
      port,
    }),
    onSuccess: (saved) => {
      queryClient.setQueryData(queryKey, saved);
      onConfigured(saved);
    },
  });
  const testMutation = useMutation({
    mutationFn: () => testBundledConnectorConnection(instance.instance_id),
    onSuccess: (result) => {
      queryClient.setQueryData(
        ["bundled-connection-test", instance.instance_id],
        result,
      );
      onTested?.(result);
    },
  });
  const valid = /^[A-Za-z0-9][A-Za-z0-9.-]{0,252}$/.test(hostname.trim()) &&
    port >= 1 && port <= 65_535;
  const error = saveMutation.error ?? testMutation.error ?? configurationQuery.error;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (valid) saveMutation.mutate();
  };

  return (
    <div className="installed-mcp-dialog-backdrop" role="presentation">
      <section
        className="installed-mcp-dialog bundled-connection-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="bundled-connection-title"
      >
        <header>
          <div>
            <p className="eyebrow">READ-ONLY CONNECTION</p>
            <h3 id="bundled-connection-title">Configure connection for {instance.display_name}</h3>
          </div>
          <button className="icon-button" type="button" aria-label="Close connection configuration" onClick={onCancel}>
            <X size={17} />
          </button>
        </header>
        <p className="muted-copy">
          Atlas stores HTTPS target metadata and a credential reference only. The connection test
          reads the Hitachi API version and cannot change the managed infrastructure.
        </p>

        {configurationQuery.isLoading ? (
          <div className="installed-mcp-status" role="status">
            <RefreshCw className="spin" size={17} /> Checking connection configuration...
          </div>
        ) : (
          <form className="installed-mcp-form" onSubmit={submit}>
            <div className="installed-mcp-form-grid">
              <label>
                Hostname or IP address
                <input
                  value={hostname}
                  maxLength={253}
                  required
                  placeholder="opscenter.example.internal"
                  onChange={(event) => setHostnameOverride(event.target.value)}
                />
              </label>
              <label>
                HTTPS port
                <input
                  type="number"
                  min={1}
                  max={65_535}
                  value={port}
                  required
                  onChange={(event) => setPortOverride(Number(event.target.value))}
                />
              </label>
            </div>
            <div className="installed-mcp-package-facts">
              <span>Protocol <strong>HTTPS</strong></span>
              <span>Credential <code>{HITACHI_AUTHORIZATION_SECRET_REFERENCE}</code></span>
            </div>
            <button className="primary-button" type="submit" disabled={!valid || saveMutation.isPending}>
              {saveMutation.isPending ? <RefreshCw className="spin" size={16} /> : <ShieldCheck size={16} />}
              {current ? "Update connection" : "Save connection"}
            </button>
          </form>
        )}

        {current && (
          <div className="bundled-connection-test">
            <div>
              <BadgeCheck size={18} />
              <span><strong>Connection configured</strong><small>{current.hostname}:{current.port}</small></span>
            </div>
            <button
              className="secondary-button"
              type="button"
              disabled={testMutation.isPending}
              onClick={() => testMutation.mutate()}
            >
              {testMutation.isPending ? <RefreshCw className="spin" size={16} /> : <Link2 size={16} />}
              Test connection
            </button>
          </div>
        )}

        {testMutation.data && (
          <div className={`installed-mcp-status ${testMutation.data.outcome === "passed" ? "" : "error-state"}`} role="status">
            {testMutation.data.outcome === "passed" ? <BadgeCheck size={18} /> : <Link2 size={18} />}
            <div>
              <strong>{testMutation.data.outcome === "passed" ? "Connection passed" : "Connection failed"}</strong>
              <span>{testMutation.data.result_code.replaceAll("_", " ")} / {testMutation.data.duration_ms} ms</span>
            </div>
          </div>
        )}

        {error && (
          <div className="installed-mcp-status error-state" role="alert">
            <Link2 size={18} />
            <div><strong>Connection operation failed</strong><span>{error instanceof Error ? error.message : "Try again"}</span></div>
          </div>
        )}

        <footer>
          <button type="button" className="secondary-button" onClick={onCancel}>Close</button>
        </footer>
      </section>
    </div>
  );
}
