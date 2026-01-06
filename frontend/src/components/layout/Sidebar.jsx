import React, { useState } from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard, BarChart3, Settings, LogOut, Sparkles, History,Layers3,MessagesSquare
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuth } from '../../store/authStore';
import ChatHistoryModal from '../ChatHistoryModal';
import { cn } from '../../lib/utils';

const Sidebar = ({ isOpen, setIsOpen, onHover }) => {
  const { logout, user } = useAuth();
  const [showHistoryModal, setShowHistoryModal] = useState(false);

  const navItems = [
    { icon: LayoutDashboard, label: 'Dashboard', path: '/app/dashboard' },
    { icon: Layers3, label: 'Datasets', path: '/app/datasets' },
    { icon: MessagesSquare, label: 'AI Chat', path: '/app/chat' },
    { icon: BarChart3, label: 'Charts', path: '/app/charts' },
    { icon: History, label: 'Chat History', path: '/app/chat-history', isButton: true, onClick: () => setShowHistoryModal(true) },
  ];

  return (
    <>
      {/* Mobile Overlay */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 backdrop-blur-sm z-30 lg:hidden"
            onClick={() => setIsOpen(false)}
          />
        )}
      </AnimatePresence>

      {/* Sidebar */}
      <motion.aside
        initial={false}
        animate={{
          width: isOpen ? 256 : (onHover ? 256 : 80),
          x: isOpen ? 0 : (onHover ? 0 : -176)
        }}
        transition={{ duration: 0.3, ease: "easeInOut" }}
        onHoverStart={() => window.innerWidth >= 1024 && onHover(true)}
        onHoverEnd={() => window.innerWidth >= 1024 && onHover(false)}
        className={cn(
          "fixed lg:sticky top-0 left-0 h-screen glass-effect border-r border-border/50 z-50"
        )}
        role="navigation"
        aria-label="Main navigation"
      >
        <div className="flex flex-col h-full p-4 overflow-y-auto">
          {/* Logo */}
          <motion.div
            className="flex items-center gap-3 mb-8"
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.1 }}
          >
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-cyan-500 flex items-center justify-center shrink-0">
              <Sparkles className="w-6 h-6 text-primary-foreground" />
            </div>
            <motion.span
              className="text-xl font-bold gradient-text whitespace-nowrap"
              initial={{ opacity: 0, width: 0 }}
              animate={{ opacity: isOpen || onHover ? 1 : 0, width: isOpen || onHover ? 'auto' : 0 }}
              transition={{ delay: 0.2 }}
            >
              DataSage
            </motion.span>
          </motion.div>

          {/* Navigation */}
          <nav className="flex-1 space-y-2" role="menubar">
            <AnimatePresence>
              {navItems.map((item, index) => (
                <motion.div
                  key={item.path}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: index * 0.05 }}
                >
                  {item.isButton ? (
                    <button
                      onClick={item.onClick}
                      className={cn(
                        "flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200 focus-visible-ring relative w-full text-left",
                        "text-muted-foreground hover:bg-accent hover:text-foreground shadow-inner-custom"
                      )}
                    >
                      <item.icon className="w-5 h-5 shrink-0" aria-hidden="true" />
                      <motion.span
                        className="whitespace-nowrap"
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: isOpen || onHover ? 1 : 0, x: 0 }}
                        transition={{ delay: 0.1 }}
                      >
                        {item.label}
                      </motion.span>
                    </button>
                  ) : (
                    <NavLink
                      to={item.path}
                      className={({ isActive }) =>
                        cn(
                          "flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200 focus-visible-ring relative shadow-inner-custom",
                          isActive
                            ? "bg-primary/10 text-primary border border-primary/20 shadow-md"
                            : "text-muted-foreground hover:bg-accent hover:text-foreground"
// Add custom inner shadow style
// You can add this to your global CSS (e.g., index.css or a relevant CSS file):
// .shadow-inner-custom { box-shadow: inset 0 2px 8px 0 rgba(0,0,0,0.18); }
                        )
                      }
                    >
                      <item.icon className="w-5 h-5 shrink-0" aria-hidden="true" />
                      <motion.span
                        className="whitespace-nowrap"
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: isOpen || onHover ? 1 : 0, x: 0 }}
                        transition={{ delay: 0.1 }}
                      >
                        {item.label}
                      </motion.span>
                    </NavLink>
                  )}
                </motion.div>
              ))}
            </AnimatePresence>
          </nav>


          {/* Logout Button */}
          <button
            onClick={logout}
            className={cn(
              "flex items-center gap-3 px-4 py-3 mt-2 rounded-lg text-muted-foreground hover:bg-accent hover:text-foreground transition-colors w-full focus-visible-ring",
              !(isOpen || onHover) && "justify-center"
            )}
            aria-label="Logout"
            style={{ marginTop: 'auto' }}
          >
            <LogOut className="w-5 h-5" />
            <span className={cn("whitespace-nowrap", !(isOpen || onHover) && "hidden")}>Logout</span>
          </button>
        </div>
      </motion.aside>

      {/* Chat History Modal */}
      <ChatHistoryModal
        isOpen={showHistoryModal}
        onClose={() => setShowHistoryModal(false)}
      />
    </>
  );
};

export default Sidebar;
