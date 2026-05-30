import { useState } from "react";
import { AdminAuditEvent, ExplorerSnapshot } from "./api";

interface AuditEventsPanelProps {
  snapshot: ExplorerSnapshot | null;
}

export function AuditEventsPanel({ snapshot }: AuditEventsPanelProps) {
  const events = snapshot?.auditEvents.audit_events ?? [];
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const selectedEvent = events.find((event) => event.event_id === selectedEventId);
  const activeEvent = selectedEvent ?? events[0] ?? null;

  return (
    <section className="panel detailPanel widePanel auditPanel">
      <div className="panelTitle">
        <h2>Audit Events</h2>
        <span>{events.length}</span>
      </div>

      <div className="auditGuard">
        <span>{snapshot?.auditEvents.environment ?? "private-devnet"}</span>
        <strong>Read only indexed audit log</strong>
      </div>

      <div className="miniTable">
        <table>
          <thead>
            <tr>
              <th>Event</th>
              <th>Actor</th>
              <th>Action</th>
              <th>Resource</th>
              <th>Resource Id</th>
            </tr>
          </thead>
          <tbody>
            {events.length > 0 ? (
              events.map((event) => (
                <tr
                  key={event.event_id}
                  className={
                    activeEvent?.event_id === event.event_id ? "selectedRow" : undefined
                  }
                >
                  <td>
                    <button
                      className="rowButton"
                      type="button"
                      onClick={() => setSelectedEventId(event.event_id)}
                    >
                      {event.event_id}
                    </button>
                  </td>
                  <td>{event.actor}</td>
                  <td>{event.action}</td>
                  <td>{event.resource_type}</td>
                  <td>{event.resource_id ?? "-"}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={5}>No audit events</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="auditDetail">
        <div className="subHeading">
          <h3>Selected Audit Event</h3>
          <span>{activeEvent ? "ready" : "idle"}</span>
        </div>
        {activeEvent ? (
          <AuditDetail event={activeEvent} />
        ) : (
          <p className="mutedText">No audit event selected</p>
        )}
      </div>
    </section>
  );
}

function AuditDetail({ event }: { event: AdminAuditEvent }) {
  return (
    <dl className="detailList">
      <Detail label="Event" value={event.event_id} compact />
      <Detail label="Actor" value={event.actor} />
      <Detail label="Action" value={event.action} />
      <Detail label="Resource" value={event.resource_type} />
      <Detail label="Resource Id" value={event.resource_id ?? "-"} compact />
      <Detail label="Environment" value={event.environment} />
    </dl>
  );
}

function Detail({
  label,
  value,
  compact = false,
}: {
  label: string;
  value: string | number;
  compact?: boolean;
}) {
  return (
    <>
      <dt>{label}</dt>
      <dd className={compact ? "mono truncate" : undefined}>{value}</dd>
    </>
  );
}
