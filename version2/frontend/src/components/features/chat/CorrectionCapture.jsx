import { useState } from "react";
import { beliefAPI } from "../../../services/api";

export default function CorrectionCapture({ belief, datasetId, onDismiss }) {
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [edited, setEdited] = useState(belief?.content || "");

  if (!belief || saved) return null;

  const handleSave = async () => {
    setSaving(true);
    try {
      await beliefAPI.create({ dataset_id: datasetId, content: edited, rule_type: belief.rule_type });
      setSaved(true);
      setTimeout(onDismiss, 1500);
    } catch (e) {
      console.error(e);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{
      margin: "8px 0",
      padding: "10px 14px",
      background: "var(--color-background-info)",
      border: "0.5px solid var(--color-border-info)",
      borderRadius: "var(--border-radius-lg)",
      fontSize: "13px",
    }}>
      <p style={{ color: "var(--color-text-info)", fontWeight: 500, margin: "0 0 6px" }}>
        Save this as a business rule?
      </p>
      <input
        value={edited}
        onChange={e => setEdited(e.target.value)}
        style={{
          width: "100%", boxSizing: "border-box",
          padding: "6px 10px", fontSize: "13px",
          marginBottom: "8px", borderRadius: "var(--border-radius-md)",
          border: "0.5px solid var(--color-border-secondary)",
          background: "var(--color-background-primary)",
          color: "var(--color-text-primary)",
        }}
      />
      <div style={{ display: "flex", gap: "8px" }}>
        <button onClick={handleSave} disabled={saving || !edited.trim()} style={{ fontSize: "12px" }}>
          {saving ? "Saving..." : saved ? "Saved ✓" : "Save rule"}
        </button>
        <button onClick={onDismiss} style={{ fontSize: "12px" }}>
          Dismiss
        </button>
      </div>
    </div>
  );
}
