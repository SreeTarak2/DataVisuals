import { create } from 'zustand';

const SIDEBAR_KEY = 'datasage-sidebar-expanded';

const useSidebarStore = create((set) => ({
    expanded: (() => {
        try {
            return JSON.parse(localStorage.getItem(SIDEBAR_KEY)) ?? false;
        } catch {
            return false;
        }
    })(),
    toggle: () => set((state) => {
        const newVal = !state.expanded;
        localStorage.setItem(SIDEBAR_KEY, JSON.stringify(newVal));
        return { expanded: newVal };
    }),
    setExpanded: (val) => set(() => {
        localStorage.setItem(SIDEBAR_KEY, JSON.stringify(val));
        return { expanded: val };
    }),
}));

export default useSidebarStore;
