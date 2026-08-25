import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Archive,
  CheckCircle2,
  Clock3,
  Database,
  LogIn,
  Pencil,
  Plus,
  RefreshCw,
  RotateCcw,
  Search,
  Server,
  ShieldCheck,
  X,
} from "lucide-react";
import {
  type FormEvent,
  type KeyboardEvent,
  useEffect,
  useRef,
  useState,
} from "react";

import {
  createInventoryDevice,
  getInventoryDevices,
  reactivateInventoryDevice,
  retireInventoryDevice,
  updateInventoryDevice,
  type InventoryDevice,
  type InventoryDeviceCreateInput,
  type InventoryDeviceLifecycle,
  type InventoryDeviceScope,
  type InventoryDeviceType,
  type InventoryDeviceUpdateInput,
} from "../../api/inventoryDevices";
import { ApiRequestError } from "../../api/client";

const DEVICE_TYPE_LABELS: Record<InventoryDeviceType, string> = {
  storage: "Storage",
  san_switch: "SAN switch",
  virtualization: "Virtualization",
  server: "Server",
  backup: "Backup",
  network: "Network",
  other: "Other",
};

type LifecycleFilter = InventoryDeviceLifecycle | "all";

function formatTimestamp(value: string): string {
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function useAccessibleDialog(
  onCancel: () => void,
  returnFocusTo: HTMLElement | null,
) {
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    const firstControl =
      dialog?.querySelector<HTMLElement>("[data-autofocus]") ??
      dialog?.querySelector<HTMLElement>(
        "button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled])",
      );
    firstControl?.focus();
    return () => returnFocusTo?.focus();
  }, [returnFocusTo]);

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      onCancel();
      return;
    }
    if (event.key !== "Tab") return;
    const focusable = Array.from(
      event.currentTarget.querySelectorAll<HTMLElement>(
        "button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])",
      ),
    );
    if (focusable.length === 0) {
      event.preventDefault();
      return;
    }
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last?.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first?.focus();
    }
  }

  return { dialogRef, handleKeyDown };
}

function DeviceCreateDialog({
  pending,
  onCancel,
  onSubmit,
}: {
  pending: boolean;
  onCancel: () => void;
  onSubmit: (input: InventoryDeviceCreateInput) => void;
}) {
  const [deviceKey, setDeviceKey] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [deviceType, setDeviceType] = useState<InventoryDeviceType>("storage");
  const [vendor, setVendor] = useState("");
  const [model, setModel] = useState("");
  const [serialNumber, setSerialNumber] = useState("");
  const [managementAddress, setManagementAddress] = useState("");
  const [purpose, setPurpose] = useState("");
  const [acknowledged, setAcknowledged] = useState(false);
  const valid =
    /^[a-z][a-z0-9_.:-]{2,127}$/.test(deviceKey) &&
    displayName.trim().length >= 3 &&
    vendor.trim().length >= 2 &&
    model.trim().length >= 1 &&
    purpose.trim().length >= 20 &&
    acknowledged;

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!valid || pending) return;
    onSubmit({
      deviceKey,
      displayName,
      deviceType,
      vendor,
      model,
      serialNumber,
      managementAddress,
      purpose,
    });
  }

  return (
    <div className="inventory-device-dialog" role="dialog" aria-modal="true" aria-labelledby="add-device-title">
      <form onSubmit={submit}>
        <div className="inventory-device-dialog-heading">
          <div>
            <p className="eyebrow">MANUAL REGISTRATION</p>
            <h3 id="add-device-title">Add infrastructure device</h3>
          </div>
          <button className="icon-button" type="button" aria-label="Close add device" onClick={onCancel}>
            <X size={17} />
          </button>
        </div>
        <div className="inventory-device-form-grid">
          <label>
            Device key
            <input
              required
              autoFocus
              value={deviceKey}
              pattern={"[a-z][a-z0-9_.:\\-]{2,127}"}
              maxLength={128}
              placeholder="storage.vsp-01"
              onChange={(event) => setDeviceKey(event.target.value.toLowerCase())}
            />
          </label>
          <label>
            Display name
            <input required value={displayName} maxLength={160} onChange={(event) => setDisplayName(event.target.value)} />
          </label>
          <label>
            Device type
            <select value={deviceType} onChange={(event) => setDeviceType(event.target.value as InventoryDeviceType)}>
              {Object.entries(DEVICE_TYPE_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
          <label>
            Vendor
            <input required value={vendor} maxLength={120} onChange={(event) => setVendor(event.target.value)} />
          </label>
          <label>
            Model
            <input required value={model} maxLength={160} onChange={(event) => setModel(event.target.value)} />
          </label>
          <label>
            Serial number
            <input value={serialNumber} maxLength={160} onChange={(event) => setSerialNumber(event.target.value)} />
          </label>
          <label className="inventory-device-form-wide">
            Management address
            <input
              value={managementAddress}
              maxLength={253}
              pattern={"[A-Za-z0-9][A-Za-z0-9.:\\-]{0,252}"}
              placeholder="vsp-01.example.net"
              onChange={(event) => setManagementAddress(event.target.value)}
            />
          </label>
          <label className="inventory-device-form-wide">
            Registration purpose
            <textarea required value={purpose} minLength={20} maxLength={1000} rows={3} onChange={(event) => setPurpose(event.target.value)} />
          </label>
        </div>
        <label className="inventory-device-acknowledgement">
          <input type="checkbox" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)} />
          <span>No credentials are stored and no infrastructure action is authorized.</span>
        </label>
        <div className="inventory-device-dialog-actions">
          <button type="button" disabled={pending} onClick={onCancel}>Cancel</button>
          <button className="inventory-device-primary" type="submit" disabled={!valid || pending}>
            {pending ? <Clock3 size={15} /> : <Plus size={15} />} Register device
          </button>
        </div>
      </form>
    </div>
  );
}

function DeviceRetireDialog({
  device,
  pending,
  onCancel,
  onSubmit,
}: {
  device: InventoryDevice;
  pending: boolean;
  onCancel: () => void;
  onSubmit: (reason: string) => void;
}) {
  const [reason, setReason] = useState("");
  const [acknowledged, setAcknowledged] = useState(false);
  const valid = reason.trim().length >= 20 && acknowledged;

  return (
    <div className="inventory-device-dialog retirement" role="dialog" aria-modal="true" aria-labelledby="retire-device-title">
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (valid && !pending) onSubmit(reason.trim());
        }}
      >
        <div className="inventory-device-dialog-heading">
          <div>
            <p className="eyebrow">LIFECYCLE CHANGE</p>
            <h3 id="retire-device-title">Retire {device.display_name}</h3>
          </div>
          <button className="icon-button" type="button" aria-label="Close retire device" onClick={onCancel}><X size={17} /></button>
        </div>
        <div className="inventory-device-retirement-impact">
          <Archive size={18} />
          <p>The record remains searchable and auditable. Active inventory use stops; the device itself is not changed.</p>
        </div>
        <label>
          Retirement reason
          <textarea autoFocus value={reason} minLength={20} maxLength={1000} rows={4} onChange={(event) => setReason(event.target.value)} />
        </label>
        <label className="inventory-device-acknowledgement">
          <input type="checkbox" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)} />
          <span>Preserve this record and stop using it as an active inventory target.</span>
        </label>
        <div className="inventory-device-dialog-actions">
          <button type="button" disabled={pending} onClick={onCancel}>Cancel</button>
          <button className="inventory-device-retire" type="submit" disabled={!valid || pending}>
            {pending ? <Clock3 size={15} /> : <Archive size={15} />} Retire device
          </button>
        </div>
      </form>
    </div>
  );
}

function DeviceEditDialog({
  device,
  pending,
  returnFocusTo,
  onCancel,
  onSubmit,
}: {
  device: InventoryDevice;
  pending: boolean;
  returnFocusTo: HTMLElement | null;
  onCancel: () => void;
  onSubmit: (changes: InventoryDeviceUpdateInput) => void;
}) {
  const [displayName, setDisplayName] = useState(device.display_name);
  const [deviceType, setDeviceType] = useState<InventoryDeviceType>(device.device_type);
  const [vendor, setVendor] = useState(device.vendor);
  const [model, setModel] = useState(device.model);
  const [serialNumber, setSerialNumber] = useState(device.serial_number ?? "");
  const [managementAddress, setManagementAddress] = useState(
    device.management_address ?? "",
  );
  const [purpose, setPurpose] = useState(device.purpose);
  const { dialogRef, handleKeyDown } = useAccessibleDialog(onCancel, returnFocusTo);
  const valid =
    displayName.trim().length >= 3 &&
    vendor.trim().length >= 2 &&
    model.trim().length >= 1 &&
    purpose.trim().length >= 20;

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!valid || pending) return;
    onSubmit({
      displayName,
      deviceType,
      vendor,
      model,
      serialNumber,
      managementAddress,
      purpose,
    });
  }

  return (
    <div
      ref={dialogRef}
      className="inventory-device-dialog"
      role="dialog"
      aria-modal="true"
      aria-labelledby="edit-device-title"
      onKeyDown={handleKeyDown}
    >
      <form onSubmit={submit}>
        <div className="inventory-device-dialog-heading">
          <div>
            <p className="eyebrow">DEVICE DETAILS</p>
            <h3 id="edit-device-title">Edit {device.display_name}</h3>
          </div>
          <button
            className="icon-button"
            type="button"
            aria-label="Close edit device"
            onClick={onCancel}
          >
            <X size={17} />
          </button>
        </div>
        <div className="inventory-device-form-grid">
          <label>
            Device key
            <input
              aria-label="Device key"
              value={device.device_key}
              disabled
              aria-describedby="device-key-note"
            />
            <small id="device-key-note">The stable device key cannot be changed.</small>
          </label>
          <label>
            Display name
            <input
              data-autofocus
              required
              value={displayName}
              maxLength={160}
              onChange={(event) => setDisplayName(event.target.value)}
            />
          </label>
          <label>
            Device type
            <select
              value={deviceType}
              onChange={(event) => setDeviceType(event.target.value as InventoryDeviceType)}
            >
              {Object.entries(DEVICE_TYPE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </label>
          <label>
            Vendor
            <input required value={vendor} maxLength={120} onChange={(event) => setVendor(event.target.value)} />
          </label>
          <label>
            Model
            <input required value={model} maxLength={160} onChange={(event) => setModel(event.target.value)} />
          </label>
          <label>
            Serial number
            <input value={serialNumber} maxLength={160} onChange={(event) => setSerialNumber(event.target.value)} />
          </label>
          <label className="inventory-device-form-wide">
            Management address
            <input
              value={managementAddress}
              maxLength={253}
              pattern={"[A-Za-z0-9][A-Za-z0-9.:\\-]{0,252}"}
              onChange={(event) => setManagementAddress(event.target.value)}
            />
          </label>
          <label className="inventory-device-form-wide">
            Inventory purpose
            <textarea required value={purpose} minLength={20} maxLength={1000} rows={3} onChange={(event) => setPurpose(event.target.value)} />
          </label>
        </div>
        <div className="inventory-device-dialog-actions">
          <button type="button" disabled={pending} onClick={onCancel}>Cancel</button>
          <button className="inventory-device-primary" type="submit" disabled={!valid || pending}>
            {pending ? <Clock3 size={15} /> : <Pencil size={15} />} Save changes
          </button>
        </div>
      </form>
    </div>
  );
}

function DeviceReactivateDialog({
  device,
  pending,
  returnFocusTo,
  onCancel,
  onSubmit,
}: {
  device: InventoryDevice;
  pending: boolean;
  returnFocusTo: HTMLElement | null;
  onCancel: () => void;
  onSubmit: () => void;
}) {
  const { dialogRef, handleKeyDown } = useAccessibleDialog(onCancel, returnFocusTo);

  return (
    <div
      ref={dialogRef}
      className="inventory-device-dialog retirement"
      role="dialog"
      aria-modal="true"
      aria-labelledby="reactivate-device-title"
      onKeyDown={handleKeyDown}
    >
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (!pending) onSubmit();
        }}
      >
        <div className="inventory-device-dialog-heading">
          <div>
            <p className="eyebrow">LIFECYCLE CHANGE</p>
            <h3 id="reactivate-device-title">Reactivate {device.display_name}</h3>
          </div>
          <button
            className="icon-button"
            type="button"
            aria-label="Close reactivate device"
            onClick={onCancel}
          >
            <X size={17} />
          </button>
        </div>
        <div className="inventory-device-reactivation-summary">
          <RotateCcw size={18} />
          <p>This returns the existing record to active inventory. Its history is preserved.</p>
        </div>
        <div className="inventory-device-dialog-actions">
          <button type="button" disabled={pending} onClick={onCancel}>Cancel</button>
          <button
            data-autofocus
            className="inventory-device-primary"
            type="submit"
            disabled={pending}
          >
            {pending ? <Clock3 size={15} /> : <RotateCcw size={15} />} Reactivate device
          </button>
        </div>
      </form>
    </div>
  );
}

export default function InventoryDeviceRegistryWorkspace({
  environmentId,
  governedSessionAvailable = true,
  onRequestEnterpriseLogin,
  organizationId,
  siteId,
}: {
  environmentId: string;
  governedSessionAvailable?: boolean;
  onRequestEnterpriseLogin?: () => void;
  organizationId: string;
  siteId: string;
}) {
  const queryClient = useQueryClient();
  const [lifecycle, setLifecycle] = useState<LifecycleFilter>("active");
  const [query, setQuery] = useState("");
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<InventoryDevice | null>(null);
  const [retiring, setRetiring] = useState<InventoryDevice | null>(null);
  const [reactivating, setReactivating] = useState<InventoryDevice | null>(null);
  const [dialogTrigger, setDialogTrigger] = useState<HTMLElement | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const scope: InventoryDeviceScope = { organizationId, environmentId, siteId };
  const inventoryQuery = useQuery({
    queryKey: ["inventory-devices", organizationId, environmentId, siteId, lifecycle, query],
    queryFn: () => getInventoryDevices({ lifecycle, query, scope }),
  });
  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ["inventory-devices"] });
  };
  const createMutation = useMutation({
    mutationFn: (input: InventoryDeviceCreateInput) => createInventoryDevice({ ...input, scope }),
    onSuccess: async (registeredDevice) => {
      setCreating(false);
      setLifecycle("active");
      setSuccessMessage(`${registeredDevice.display_name} was added to active inventory.`);
      await refresh();
    },
  });
  const retireMutation = useMutation({
    mutationFn: ({ device, reason }: { device: InventoryDevice; reason: string }) =>
      retireInventoryDevice({ device, reason }),
    onSuccess: async (retiredDevice) => {
      setRetiring(null);
      setSuccessMessage(
        `${retiredDevice.display_name} was removed from active inventory and retained as retired.`,
      );
      await refresh();
    },
  });
  const updateMutation = useMutation({
    mutationFn: ({
      device,
      changes,
    }: {
      device: InventoryDevice;
      changes: InventoryDeviceUpdateInput;
    }) => updateInventoryDevice({ device, changes }),
    onSuccess: async (updatedDevice) => {
      setEditing(null);
      setSuccessMessage(`${updatedDevice.display_name} was updated.`);
      await refresh();
    },
  });
  const reactivateMutation = useMutation({
    mutationFn: (device: InventoryDevice) => reactivateInventoryDevice({ device }),
    onSuccess: async (reactivatedDevice) => {
      setReactivating(null);
      setLifecycle("active");
      setSuccessMessage(`${reactivatedDevice.display_name} returned to active inventory.`);
      await refresh();
    },
  });
  const inventory = inventoryQuery.data;
  const activeCount = inventory?.devices.filter((item) => item.lifecycle === "active").length ?? 0;
  const lifecycleError =
    createMutation.error ??
    updateMutation.error ??
    retireMutation.error ??
    reactivateMutation.error;
  const lifecycleAccessDenied =
    lifecycleError instanceof ApiRequestError &&
    (lifecycleError.status === 401 || lifecycleError.status === 403);

  return (
    <section className="workspace-section inventory-device-registry" aria-labelledby="inventory-device-title">
      <div className="section-heading inventory-device-heading">
        <div>
          <p className="eyebrow">DEVICE REGISTRY</p>
          <h2 id="inventory-device-title">Registered infrastructure</h2>
          <p>Authorized lifecycle records for the current organization and environment.</p>
        </div>
        <div className="inventory-device-heading-actions">
          {inventory && (
            <span className={`inventory-persistence ${inventory.durable ? "durable" : "memory"}`}>
              <Database size={14} /> {inventory.durable ? "Durable store" : "Development memory"}
            </span>
          )}
          <button
            type="button"
            disabled={!governedSessionAvailable}
            title={
              governedSessionAvailable
                ? "Add infrastructure device"
                : "Sign in to manage devices"
            }
            onClick={() => {
              createMutation.reset();
              setSuccessMessage(null);
              setCreating(true);
            }}
          >
            <Plus size={15} /> Add device
          </button>
        </div>
      </div>

      <div className="inventory-device-toolbar">
        <div className="inventory-device-segments" role="group" aria-label="Device lifecycle filter">
          {(["active", "retired", "all"] as const).map((value) => (
            <button key={value} type="button" aria-pressed={lifecycle === value} onClick={() => setLifecycle(value)}>
              {value === "all" ? "All" : value.charAt(0).toUpperCase() + value.slice(1)}
            </button>
          ))}
        </div>
        <label className="inventory-device-search">
          <Search size={15} />
          <span className="sr-only">Search registered devices</span>
          <input value={query} maxLength={160} placeholder="Search devices" onChange={(event) => setQuery(event.target.value)} />
        </label>
      </div>

      {!governedSessionAvailable && (
        <div className="inventory-device-status enterprise-login-required" role="status">
          <LogIn size={17} />
          <div>
            <strong>Sign in to manage inventory devices</strong>
            <span>Username and password sign-in enables authorized registration and retirement.</span>
          </div>
          {onRequestEnterpriseLogin && (
            <button type="button" onClick={onRequestEnterpriseLogin}>
              <LogIn size={15} /> Sign in to manage
            </button>
          )}
        </div>
      )}

      {inventoryQuery.isLoading && <div className="inventory-device-status"><Clock3 size={17} /> Loading device registry</div>}
      {inventoryQuery.isError && (
        <div className="inventory-device-status error-state" role="alert">
          <AlertTriangle size={17} />
          <span>Device registry is unavailable.</span>
          <button type="button" onClick={() => void inventoryQuery.refetch()}>
            <RefreshCw size={15} /> Retry
          </button>
        </div>
      )}
      {lifecycleAccessDenied && (
        <div className="inventory-device-status error-state" role="alert">
          <LogIn size={17} />
          <span>Your session can no longer manage inventory devices.</span>
          {onRequestEnterpriseLogin && (
            <button type="button" onClick={onRequestEnterpriseLogin}>
              <LogIn size={15} /> Sign in again
            </button>
          )}
        </div>
      )}
      {createMutation.isError && !lifecycleAccessDenied && <div className="inventory-device-status error-state" role="alert"><AlertTriangle size={17} /> Device registration failed. Review the scope and unique device key.</div>}
      {updateMutation.isError && !lifecycleAccessDenied && <div className="inventory-device-status error-state" role="alert"><AlertTriangle size={17} /> Device update failed. Refresh and review the current version.</div>}
      {retireMutation.isError && !lifecycleAccessDenied && <div className="inventory-device-status error-state" role="alert"><AlertTriangle size={17} /> Device retirement failed. Refresh and review the current version.</div>}
      {reactivateMutation.isError && !lifecycleAccessDenied && <div className="inventory-device-status error-state" role="alert"><AlertTriangle size={17} /> Device reactivation failed. Refresh and review the current version.</div>}
      {successMessage && (
        <div className="inventory-device-status success-state" role="status" aria-live="polite">
          <CheckCircle2 size={17} /> {successMessage}
        </div>
      )}

      {inventory && inventory.devices.length === 0 && (
        <div className="inventory-device-empty">
          <Server size={20} />
          <div><strong>No matching registered devices</strong><p>Add a device or change the lifecycle filter.</p></div>
          {governedSessionAvailable ? (
            <button
              type="button"
              onClick={() => {
                createMutation.reset();
                setSuccessMessage(null);
                setCreating(true);
              }}
            >
              <Plus size={15} /> Add device
            </button>
          ) : null}
        </div>
      )}
      {inventory && inventory.devices.length > 0 && (
        <div className="table-wrap inventory-device-table-wrap">
          <table className="inventory-device-table">
            <thead><tr><th>Device</th><th>Type</th><th>Management</th><th>Lifecycle</th><th>Updated</th><th>Manage</th></tr></thead>
            <tbody>
              {inventory.devices.map((device) => (
                <tr key={device.device_id}>
                  <td data-label="Device"><div className="inventory-device-identity"><Server size={17} /><span><strong>{device.display_name}</strong><small>{device.vendor} {device.model}</small><code>{device.device_key}</code></span></div></td>
                  <td data-label="Type">{DEVICE_TYPE_LABELS[device.device_type]}</td>
                  <td data-label="Management"><span className="inventory-device-management">{device.management_address ?? "Not declared"}</span><small>{device.serial_number ?? "No serial"}</small></td>
                  <td data-label="Lifecycle"><span className={`inventory-device-lifecycle ${device.lifecycle}`}>{device.lifecycle === "active" ? <CheckCircle2 size={14} /> : <Archive size={14} />}{device.lifecycle}</span></td>
                  <td data-label="Updated">{formatTimestamp(device.updated_at)}</td>
                  <td data-label="Manage">
                    {device.lifecycle === "active" ? (
                      <div className="inventory-device-row-actions">
                        <button
                          className="inventory-device-row-action"
                          type="button"
                          disabled={!governedSessionAvailable}
                          title={governedSessionAvailable ? "Edit device details" : "Sign in to manage devices"}
                          aria-label={`Edit ${device.display_name}`}
                          onClick={(event) => {
                            updateMutation.reset();
                            setSuccessMessage(null);
                            setDialogTrigger(event.currentTarget);
                            setEditing(device);
                          }}
                        >
                          <Pencil size={15} /> Edit
                        </button>
                        <button
                          className="inventory-device-row-action retirement-action"
                          type="button"
                          disabled={!governedSessionAvailable}
                          title={
                            governedSessionAvailable
                              ? "Remove from active inventory and preserve audit history"
                              : "Sign in to manage devices"
                          }
                          aria-label={`Retire ${device.display_name}`}
                          onClick={() => {
                            retireMutation.reset();
                            setSuccessMessage(null);
                            setRetiring(device);
                          }}
                        >
                          <Archive size={15} /> Retire
                        </button>
                      </div>
                    ) : (
                      <div className="inventory-device-row-actions">
                        <button
                          className="inventory-device-row-action"
                          type="button"
                          disabled={!governedSessionAvailable}
                          title={governedSessionAvailable ? "Return to active inventory" : "Sign in to manage devices"}
                          aria-label={`Reactivate ${device.display_name}`}
                          onClick={(event) => {
                            reactivateMutation.reset();
                            setSuccessMessage(null);
                            setDialogTrigger(event.currentTarget);
                            setReactivating(device);
                          }}
                        >
                          <RotateCcw size={15} /> Reactivate
                        </button>
                        <span className="inventory-device-retired-label">History retained</span>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {inventory && (
        <div className="inventory-device-boundary">
          <ShieldCheck size={15} />
          <span>{activeCount} active in this result. Inventory lifecycle changes do not execute infrastructure actions.</span>
        </div>
      )}
      {creating && <DeviceCreateDialog pending={createMutation.isPending} onCancel={() => setCreating(false)} onSubmit={(input) => createMutation.mutate(input)} />}
      {editing && (
        <DeviceEditDialog
          device={editing}
          pending={updateMutation.isPending}
          returnFocusTo={dialogTrigger}
          onCancel={() => setEditing(null)}
          onSubmit={(changes) => updateMutation.mutate({ device: editing, changes })}
        />
      )}
      {retiring && <DeviceRetireDialog device={retiring} pending={retireMutation.isPending} onCancel={() => setRetiring(null)} onSubmit={(reason) => retireMutation.mutate({ device: retiring, reason })} />}
      {reactivating && (
        <DeviceReactivateDialog
          device={reactivating}
          pending={reactivateMutation.isPending}
          returnFocusTo={dialogTrigger}
          onCancel={() => setReactivating(null)}
          onSubmit={() => reactivateMutation.mutate(reactivating)}
        />
      )}
    </section>
  );
}
