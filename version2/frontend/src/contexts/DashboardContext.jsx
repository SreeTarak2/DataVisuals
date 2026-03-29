import React, { createContext, useContext } from 'react';

const DashboardContext = createContext(null);

export const useDashboardContext = () => {
  const context = useContext(DashboardContext);
  if (!context) {
    return {
      onRegenerate: null,
      MAX_REDESIGNS: null,
    };
  }
  return context;
};

export const DashboardProvider = ({ children, onRegenerate, MAX_REDESIGNS }) => {
  return (
    <DashboardContext.Provider value={{ onRegenerate, MAX_REDESIGNS }}>
      {children}
    </DashboardContext.Provider>
  );
};
