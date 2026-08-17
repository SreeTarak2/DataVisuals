import { create } from 'zustand';
import { persist } from 'zustand/middleware';

/* ─── Card type icon/color registry ─── */
export const CARD_TYPES = {
  chart: { icon: 'BarChart3', label: 'Chart', accent: '#3b82f6', defaultWidth: 480, defaultHeight: 360 },
  kpi: { icon: 'Target', label: 'KPI', accent: '#10b981', defaultWidth: 280, defaultHeight: 180 },
  text: { icon: 'FileText', label: 'Note', accent: '#f59e0b', defaultWidth: 320, defaultHeight: 220 },
  table: { icon: 'Table', label: 'Table', accent: '#8b5cf6', defaultWidth: 520, defaultHeight: 300 },
};

/* ─── Generates a new card with defaults for type ─── */
function createCard(type, cardsCount) {
  const meta = CARD_TYPES[type] || CARD_TYPES.text;
  const offset = 40 + cardsCount * 28;
  return {
    id: `card-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
    type,
    x: 120 + (offset % 500),
    y: 120 + Math.floor(offset / 500) * 30,
    width: meta.defaultWidth,
    height: meta.defaultHeight,
    title: `New ${meta.label}`,
    config: getDefaultConfig(type),
  };
}

function getDefaultConfig(type) {
  switch (type) {
    case 'chart':
      return { chart_type: 'bar', columns: [], datasetId: null, yColumns: [], groupBy: null };
    case 'kpi':
      return { column: '', aggregation: 'sum', format: 'number', datasetId: null };
    case 'text':
      return { content: '## Note\n\nDouble-click to edit this note. You can use **markdown** formatting.' };
    case 'table':
      return { columns: [], limit: 50, datasetId: null };
    default:
      return {};
  }
}

const useCanvasStore = create(
  persist(
    (set, get) => ({
      // ── State ──
      cards: [],
      zoom: 1,
      stagePosition: { x: 0, y: 0 },
      selectedCardId: null,
      linkedDatasetId: null, // The dataset currently linked to the playground
      linkedDatasetData: [],  // Cached preview data from linked dataset

      // ── Card actions ──
      addCard: (type = 'text') =>
        set((state) => {
          const newCard = createCard(type, state.cards.length);
          return { cards: [...state.cards, newCard], selectedCardId: newCard.id };
        }),

      updateCard: (id, newProps) =>
        set((state) => ({
          cards: state.cards.map((c) => (c.id === id ? { ...c, ...newProps } : c)),
        })),

      updateCardConfig: (id, configPatch) =>
        set((state) => ({
          cards: state.cards.map((c) =>
            c.id === id ? { ...c, config: { ...c.config, ...configPatch } } : c
          ),
        })),

      deleteCard: (id) =>
        set((state) => ({
          cards: state.cards.filter((c) => c.id !== id),
          selectedCardId: state.selectedCardId === id ? null : state.selectedCardId,
        })),

      duplicateCard: (id) =>
        set((state) => {
          const source = state.cards.find((c) => c.id === id);
          if (!source) return state;
          const dup = {
            ...source,
            id: `card-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
            title: `${source.title} (copy)`,
            x: source.x + 24,
            y: source.y + 24,
          };
          return { cards: [...state.cards, dup], selectedCardId: dup.id };
        }),

      clearAllCards: () => set({ cards: [], selectedCardId: null }),

      // ── Canvas state actions ──
      setZoom: (zoom) => set({ zoom }),
      setStagePosition: (pos) => set({ stagePosition: pos }),
      setSelectedCardId: (id) => set({ selectedCardId: id }),
      clearSelection: () => set({ selectedCardId: null }),

      // ── Dataset linking ──
      setLinkedDataset: (datasetId, data = []) =>
        set({ linkedDatasetId: datasetId, linkedDatasetData: data }),

      clearLinkedDataset: () =>
        set({ linkedDatasetId: null, linkedDatasetData: [] }),

      // ── Get available columns from linked dataset ──
      getLinkedColumns: () => {
        const { linkedDatasetData } = get();
        if (!Array.isArray(linkedDatasetData) || linkedDatasetData.length === 0) return [];
        return Object.keys(linkedDatasetData[0] || {}).filter((k) => k !== '_id');
      },
    }),
    {
      name: 'signal-playground-canvas',
      // Only persist cards and dataset link — not transient view state
      partialize: (state) => ({
        cards: state.cards,
        linkedDatasetId: state.linkedDatasetId,
      }),
    }
  )
);

export default useCanvasStore;
