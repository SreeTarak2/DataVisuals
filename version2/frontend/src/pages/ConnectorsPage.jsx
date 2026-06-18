import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Database, 
  FileText,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import SearchInput from '../components/ui/SearchInput';
import UploadModal from '../components/features/datasets/UploadModal';
import { useTheme } from '../store/themeStore';
import { cn } from "../lib/utils";

// Supported Connectors & Files
const CONNECTORS = [
  { id: 'postgres', name: 'PostgreSQL', desc: 'Connect your PostgreSQL database for instant AI analysis', tag: 'Database', isNew: false, image: '/postgres.png', color: 'text-blue-400', bg: 'bg-white/5' },
  { id: 'mysql', name: 'MySQL', desc: 'Connect your MySQL database for instant AI analysis', tag: 'Database', isNew: false, image: '/mysql.png', color: 'text-orange-400', bg: 'bg-white/5' },
  { id: 'mongodb', name: 'MongoDB', desc: 'Connect your MongoDB database for instant AI analysis', tag: 'Database', isNew: false, image: '/mongodb.png', color: 'text-green-500', bg: 'bg-white/5' },
  { id: 'csv', name: 'CSV', desc: 'Upload CSV files to instantly analyze your structured data', tag: 'File', isNew: false, icon: FileText, color: 'text-green-400', bg: 'bg-green-400/10' },
  { id: 'excel', name: 'Excel', desc: 'Upload Excel spreadsheets (.xlsx, .xls) for automated insights', tag: 'File', isNew: false, image: '/excel.png', color: 'text-emerald-500', bg: 'bg-emerald-500/10' },
  { id: 'tsv', name: 'TSV', desc: 'Upload TSV files to run powerful statistical analysis', tag: 'File', isNew: false, icon: FileText, color: 'text-teal-400', bg: 'bg-teal-400/10' },
  { id: 'gsheets', name: 'Google Sheets', desc: 'Live connection to your Google Sheets', tag: 'Integration', isNew: false, image: '/google-sheets.png', color: 'text-emerald-500', bg: 'bg-emerald-500/10' },
  { id: 'supabase', name: 'Supabase', desc: 'Connect your Supabase Postgres database for instant AI analysis', tag: 'Database', isNew: true, image: '/supabase.png', color: 'text-emerald-400', bg: 'bg-emerald-400/10' },
];

const TABS = ['All', 'Databases', 'Files', 'Integrations'];

const FILE_CONNECTOR_IDS = ['csv', 'excel', 'tsv'];

const ConnectorsPage = () => {
  const navigate = useNavigate();
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';
  const [activeTab, setActiveTab] = useState('All');
  const [searchQuery, setSearchQuery] = useState('');
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [uploadFileOnly, setUploadFileOnly] = useState(true);

  const filteredConnectors = CONNECTORS.filter(conn => {
    const matchesTab = activeTab === 'All' || conn.tag === (activeTab === 'Databases' ? 'Database' : activeTab === 'Files' ? 'File' : 'Integration');
    const matchesSearch = conn.name.toLowerCase().includes(searchQuery.toLowerCase()) || conn.desc.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesTab && matchesSearch;
  });

  return (
    <div className={cn(
      "h-full flex flex-col overflow-hidden relative selection:bg-orange-500/20 selection:text-white transition-colors duration-300",
      isDark ? "bg-[#0D0D0F]" : "bg-gray-50"
    )}>
      {/* Background Ambient Glows */}
      <div className="absolute top-0 left-1/3 w-[500px] h-[500px] bg-orange-500/[0.02] rounded-full blur-[140px] pointer-events-none animate-pulse-soft" />

      <main className="flex-1 overflow-y-auto px-8 py-16 md:px-16 lg:px-24">
        <div className="mx-auto max-w-[1100px] space-y-16">
          
          {/* Header */}
          <header className="space-y-3 animate-in fade-in slide-in-from-top-4 duration-700">
            <div className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-orange-500" />
              <span className="text-[11px] font-semibold tracking-wider text-orange-500/80 uppercase">Integrations Registry</span>
            </div>
            <h1 className={cn(
              "text-4xl font-semibold tracking-tight transition-colors duration-300",
              isDark ? "text-white" : "text-gray-900"
            )}>
              Connectors & MCPs
            </h1>
            <p className={cn(
              "text-sm max-w-xl leading-relaxed transition-colors duration-300",
              isDark ? "text-gray-400" : "text-gray-600"
            )}>
              Connect your local datasets or live data warehouses. Your schemas are automatically indexed into the intelligence catalog.
            </p>
          </header>

          {/* Add Connectors Section */}
          <section className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700 delay-300">
            {/* Filters and Search */}
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
              <div className={cn(
                "flex items-center gap-1.5 p-1 rounded-lg border transition-colors duration-300",
                isDark ? "bg-[#131316] border-white/[0.05]" : "bg-gray-100 border-gray-200"
              )}>
                {TABS.map(tab => (
                  <button
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    className={cn(
                      "px-4 py-1.5 text-xs font-semibold rounded-md transition-all duration-200 cursor-pointer",
                      activeTab === tab 
                        ? "bg-orange-600 text-white shadow-md shadow-orange-950/20" 
                        : isDark
                          ? "text-gray-400 hover:text-white hover:bg-white/5"
                          : "text-gray-500 hover:text-gray-900 hover:bg-gray-200"
                    )}
                  >
                    {tab}
                  </button>
                ))}
              </div>

              <SearchInput 
                placeholder="Search catalog..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                width="100%"
                className="w-full md:w-72"
                style={{
                  paddingTop: '8px',
                  paddingBottom: '8px',
                }}
              />
            </div>

            {/* Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              <AnimatePresence mode="popLayout">
                {filteredConnectors.map((conn) => (
                  <motion.div
                    layout
                    initial={{ opacity: 0, scale: 0.98 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.98 }}
                    transition={{ duration: 0.2 }}
                    key={conn.id}
                    onClick={() => {
                      if (FILE_CONNECTOR_IDS.includes(conn.id)) {
                        setUploadFileOnly(true);
                        setIsUploadModalOpen(true);
                      } else {
                        navigate(`/app/connectors/${conn.id}`);
                      }
                    }}
                    className={cn(
                      "group flex gap-5 p-6 rounded-xl border transition-all duration-300 cursor-pointer",
                      isDark
                        ? "bg-[#131316] border-white/[0.04] hover:bg-[#18181D] hover:border-white/[0.08]"
                        : "bg-white border-gray-200 hover:bg-gray-50 hover:border-gray-300",
                      "hover:-translate-y-0.5"
                    )}
                  >
                    <div className={cn("w-12 h-12 shrink-0 rounded-xl flex items-center justify-center overflow-hidden transition-transform duration-300 group-hover:scale-105", conn.bg, conn.color)}>
                      {conn.image ? (
                        <img src={conn.image} alt={conn.name} className="w-8 h-8 object-contain" />
                      ) : (
                        <conn.icon size={24} />
                      )}
                    </div>
                    <div className="flex flex-col flex-1">
                      <div className="flex items-center gap-2">
                        <h3 className={cn(
                          "text-base font-semibold tracking-tight transition-colors duration-300",
                          isDark ? "text-white" : "text-gray-900"
                        )}>{conn.name}</h3>
                        {conn.isNew && (
                          <span className="text-[9px] font-bold text-orange-500 bg-orange-500/10 px-1.5 py-0.5 rounded uppercase tracking-wider">
                            New
                          </span>
                        )}
                      </div>
                      <p className={cn(
                        "text-xs mt-1.5 leading-relaxed line-clamp-2 transition-colors duration-300",
                        isDark ? "text-gray-400" : "text-gray-600"
                      )}>
                        {conn.desc}
                      </p>
                      <div className={cn(
                        "mt-4 pt-4 flex justify-between items-center transition-colors duration-300",
                        isDark ? "border-t border-white/[0.03]" : "border-t border-gray-200"
                      )}>
                        <span className={cn(
                          "inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold tracking-wider uppercase transition-colors duration-300",
                          isDark
                            ? "bg-white/[0.03] text-gray-400 group-hover:bg-white/[0.06] group-hover:text-gray-300"
                            : "bg-gray-100 text-gray-500 group-hover:bg-gray-200 group-hover:text-gray-700"
                        )}>
                          {conn.tag}
                        </span>
                        <span className="text-[11px] text-orange-500/0 group-hover:text-orange-500 transition-all duration-300 font-semibold flex items-center gap-1">
                          Configure &rarr;
                        </span>
                      </div>
                    </div>
                  </motion.div>
                ))}
              </AnimatePresence>
              
              {filteredConnectors.length === 0 && (
                <div className={cn(
                  "col-span-full py-16 text-center text-sm transition-colors duration-300",
                  isDark ? "text-gray-500" : "text-gray-400"
                )}>
                  No connectors found matching &ldquo;{searchQuery}&rdquo;
                </div>
              )}
            </div>
            
            {/* Need another connection? */}
            <div className={cn(
              "mt-12 pt-12 border-t text-center transition-colors duration-300",
              isDark ? "border-white/[0.04]" : "border-gray-200"
            )}>
              <p className={cn(
                "text-sm transition-colors duration-300",
                isDark ? "text-gray-500" : "text-gray-400"
              )}>
                Need another connection? <button className="text-orange-500 hover:text-orange-400 hover:underline font-semibold transition-colors cursor-pointer">Let us know</button>
              </p>
            </div>
          </section>
        </div>
      </main>

      {/* Upload Modal */}
      <UploadModal
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        fileOnly={uploadFileOnly}
      />
    </div>
  );
};

export default ConnectorsPage;
