import { create } from 'zustand';

const useDashboardActionStore = create((set) => ({
  // Dashboard redesign state
  isRedesigning: false,
  redesignAttempts: 0,
  onRegenerate: null,
  MAX_REDESIGNS: 5,

  // Insights refresh state
  insightsLoading: false,
  onInsightsRefresh: null,

  // Dashboard setters
  setRedesigning: (isRedesigning) => set({ isRedesigning }),
  setRedesignAttempts: (attempts) => set({ redesignAttempts: attempts }),
  setOnRegenerate: (callback) => set({ onRegenerate: callback }),
  setMaxRedesigns: (max) => set({ MAX_REDESIGNS: max }),
  resetRedesignState: () => set({ isRedesigning: false, redesignAttempts: 0 }),

  // Insights setters
  setInsightsLoading: (loading) => set({ insightsLoading: loading }),
  setOnInsightsRefresh: (callback) => set({ onInsightsRefresh: callback }),

  // Cross-chart filtering
  crossFilter: null,
  setCrossFilter: (filter) => set({ crossFilter: filter }),
}));

export default useDashboardActionStore;
