import { create } from "zustand";

/**
 * Persona store — audience-aware dashboard emphasis.
 *
 * "Same dataset, different audience → different dashboard."
 * The selected persona (explorer | ceo | analyst | marketing | ops) is keyed
 * per dataset so switching it in one project never affects another. The
 * Dashboard's useMetrics hook reads this store and refetches KPIs with the
 * persona param, which the backend uses to re-rank KPI selection.
 */
const usePersonaStore = create((set) => ({
  personas: {}, // datasetId -> persona key

  setPersona: (datasetId, persona) =>
    set((s) => ({
      personas: {
        ...s.personas,
        [datasetId]: persona,
      },
    })),
}));

export default usePersonaStore;
