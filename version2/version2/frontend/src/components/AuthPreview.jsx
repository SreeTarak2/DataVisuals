import React from "react";
import { motion } from "framer-motion";
import { TrendingUp, CheckCircle2 } from "lucide-react";
import { Card } from "@/components/ui/card";

export default function AuthPreview() {
    return (
        <div className="hidden md:flex md:w-1/2 relative bg-[#09090b] overflow-hidden p-6 lg:p-12 items-center justify-center">
            <div className="absolute top-1/4 -right-20 w-80 h-80 bg-indigo-600/20 rounded-full blur-[120px]" />
            <div className="absolute bottom-1/4 -left-20 w-80 h-80 bg-purple-600/10 rounded-full blur-[120px]" />

            <div className="relative w-full max-w-2xl space-y-6">
                <div className="grid grid-cols-6 gap-4 lg:gap-6">
                    {/* Sales Revenue - Span 3x1 */}
                    <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.1 }}
                        className="col-span-6 md:col-span-3 lg:col-span-3"
                    >
                        <Card className="bg-zinc-900/40 border-zinc-800/50 backdrop-blur-xl p-4 lg:p-6 space-y-4 h-full">
                            <div className="flex items-center justify-between">
                                <span className="text-[10px] lg:text-xs text-zinc-500 font-medium uppercase tracking-wider">
                                    Sales Revenue
                                </span>
                                <div className="p-1.5 bg-indigo-500/10 rounded">
                                    <TrendingUp className="w-4 h-4 text-indigo-400" />
                                </div>
                            </div>
                            <div>
                                <div className="text-2xl lg:text-3xl font-bold text-white">
                                    $5.832
                                </div>
                                <div className="text-[10px] lg:text-xs text-zinc-500 mt-1">
                                    Monthly revenue <span className="text-zinc-400">-$421</span>
                                </div>
                            </div>
                            <div className="flex items-end gap-1.5 h-10 lg:h-12">
                                {[40, 60, 45, 80, 55, 70].map((h, i) => (
                                    <div
                                        key={i}
                                        className={`flex-1 rounded-[5px] ${i === 3 ? "bg-indigo-500" : "bg-zinc-800"
                                            }`}
                                        style={{ height: `${h}%` }}
                                    />
                                ))}
                            </div>
                        </Card>
                    </motion.div>

                    {/* Sales Targets - Span 3x1 */}
                    <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.2 }}
                        className="col-span-6 md:col-span-3 lg:col-span-3"
                    >
                        <Card className="bg-zinc-900/40 border-zinc-800/50 backdrop-blur-xl p-4 lg:p-6 space-y-4 h-full">
                            <div className="flex items-center justify-between">
                                <span className="text-[10px] lg:text-xs text-zinc-500 font-medium uppercase tracking-wider">
                                    Sales Targets
                                </span>
                                <div className="p-1.5 bg-emerald-500/10 rounded">
                                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                                </div>
                            </div>
                            <div className="flex items-center gap-3 lg:gap-4">
                                <div className="relative w-12 h-12 lg:w-14 lg:h-14 flex items-center justify-center shrink-0 text-white">
                                    <svg className="w-full h-full -rotate-90">
                                        <circle
                                            cx="28"
                                            cy="28"
                                            r="24"
                                            fill="none"
                                            stroke="currentColor"
                                            strokeWidth="5"
                                            className="text-zinc-800"
                                        />
                                        <circle
                                            cx="28"
                                            cy="28"
                                            r="24"
                                            fill="none"
                                            stroke="currentColor"
                                            strokeWidth="5"
                                            className="text-indigo-500"
                                            strokeDasharray="150"
                                            strokeDashoffset="30"
                                        />
                                    </svg>
                                    <span className="absolute text-[8px] lg:text-[10px] font-bold">
                                        80%
                                    </span>
                                </div>
                                <div>
                                    <div className="text-base lg:text-lg font-bold text-white">
                                        3,415{" "}
                                        <span className="text-zinc-500 text-[10px] lg:text-xs font-normal">
                                            / 4,000
                                        </span>
                                    </div>
                                    <p className="text-[10px] lg:text-xs text-zinc-500 mt-1">
                                        Almost there!
                                    </p>
                                </div>
                            </div>
                        </Card>
                    </motion.div>

                    {/* Won by Type - Span 4x1 */}
                    <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.3 }}
                        className="col-span-6 md:col-span-4 lg:col-span-4"
                    >
                        <Card className="bg-zinc-900/40 border-zinc-800/50 backdrop-blur-xl p-4 lg:p-6 space-y-3 h-full">
                            <span className="text-[10px] lg:text-xs text-zinc-500 font-medium uppercase tracking-wider">
                                Closed Won by Type
                            </span>
                            <div className="flex flex-col lg:flex-row lg:justify-between lg:items-end gap-4 lg:gap-0">
                                <div>
                                    <div className="text-2xl lg:text-3xl font-bold text-white">
                                        $11,680
                                    </div>
                                    <div className="text-[10px] lg:text-xs text-zinc-500 mt-1">
                                        Growth <span className="text-indigo-400">+$6,450</span>
                                    </div>
                                </div>
                                <div className="flex gap-1 items-end h-12 lg:h-16">
                                    {[20, 40, 30, 90, 60].map((h, i) => (
                                        <div
                                            key={i}
                                            className="w-2.5 lg:w-3 bg-zinc-800 rounded-t-sm relative overflow-hidden"
                                            style={{ height: `${h}%` }}
                                        >
                                            <div className="absolute inset-0 bg-gradient-to-t from-indigo-500/40 to-transparent" />
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </Card>
                    </motion.div>

                    {/* Segmentation - Span 2x1 */}
                    <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.4 }}
                        className="col-span-6 md:col-span-2 lg:col-span-2"
                    >
                        <Card className="bg-zinc-900/40 border-zinc-800/50 backdrop-blur-xl p-4 lg:p-6 flex flex-col justify-center space-y-3 lg:space-y-4 h-full">
                            <div className="flex items-center gap-2 lg:gap-3">
                                <div className="relative w-10 h-10 lg:w-12 lg:h-12 flex items-center justify-center shrink-0 text-white">
                                    <svg className="w-full h-full -rotate-90">
                                        <circle
                                            cx="24"
                                            cy="24"
                                            r="20"
                                            fill="none"
                                            stroke="currentColor"
                                            strokeWidth="4"
                                            className="text-zinc-800"
                                        />
                                        <circle
                                            cx="24"
                                            cy="24"
                                            r="20"
                                            fill="none"
                                            stroke="currentColor"
                                            strokeWidth="4"
                                            className="text-indigo-500"
                                            strokeDasharray="125"
                                            strokeDashoffset="25"
                                        />
                                    </svg>
                                </div>
                                <div className="text-sm lg:text-base font-bold text-white">
                                    2.7k{" "}
                                    <span className="text-zinc-500 block text-[8px] lg:text-[10px] font-normal">
                                        Users
                                    </span>
                                </div>
                            </div>
                            <div className="space-y-1.5 lg:space-y-2">
                                <div className="flex justify-between text-[8px] lg:text-[10px]">
                                    <span className="text-zinc-400">SMB</span>
                                    <span className="text-zinc-200">60%</span>
                                </div>
                                <div className="w-full bg-zinc-800 h-1 rounded-full overflow-hidden">
                                    <div className="bg-indigo-500 h-full w-[60%]" />
                                </div>
                            </div>
                        </Card>
                    </motion.div>
                </div>

                <div className="text-center space-y-3 lg:space-y-4 pt-4 lg:pt-8">
                    <h2 className="text-3xl lg:text-4xl font-bold tracking-tight bg-gradient-to-b from-white to-zinc-500 bg-clip-text text-transparent">
                        Transform Data into Insights
                    </h2>
                    <p className="text-zinc-400 text-sm lg:text-base max-w-md mx-auto leading-relaxed">
                        Make informed decisions with DataSage's powerful analytics.
                    </p>
                    <div className="flex justify-center gap-2 pt-2 lg:pt-4">
                        <div className="w-1.5 h-1.5 rounded-full bg-white" />
                        <div className="w-1.5 h-1.5 rounded-full bg-zinc-800" />
                        <div className="w-1.5 h-1.5 rounded-full bg-zinc-800" />
                    </div>
                </div>
            </div>
        </div>
    );
}
