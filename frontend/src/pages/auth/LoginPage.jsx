import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Mail, Lock, ArrowRight, Eye, EyeOff, Loader2 } from 'lucide-react';
import { useAuth } from '@/store/authStore';
import toast from 'react-hot-toast';
import GlassPanel from '@/components/ui/GlassPanel';
import NeonButton from '@/components/ui/NeonButton';
import ParticleBackground from '@/components/ui/ParticleBackground';

const AntigravityLogin = () => {
    const [showPassword, setShowPassword] = useState(false);
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [isLoading, setIsLoading] = useState(false);

    const { login } = useAuth();
    const navigate = useNavigate();

    const handleLogin = async (e) => {
        e.preventDefault();
        if (!email || !password) {
            toast.error("Please fill in all fields");
            return;
        }

        setIsLoading(true);
        try {
            const result = await login(email, password);
            if (result.success) {
                toast.success("Welcome, Commander.");
                // Warpspeed effect could be triggered here before navigation
                setTimeout(() => navigate("/dashboard"), 500);
            } else {
                toast.error(result.error || "Access Denied");
            }
        } catch (error) {
            toast.error("System Error");
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="relative min-h-screen w-full flex items-center justify-center overflow-hidden bg-noir text-pearl">
            {/* Background */}
            <ParticleBackground />

            {/* Login Portal */}
            <motion.div
                initial={{ opacity: 0, scale: 0.9, y: 20 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                transition={{ duration: 0.6, ease: "easeOut" }}
                className="relative z-10 w-full max-w-md px-4"
            >
                <GlassPanel className="border-t border-pearl/20 shadow-[0_0_50px_-10px_rgba(18,44,79,0.5)]">
                    <div className="text-center mb-8">
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            transition={{ delay: 0.3 }}
                            className="inline-block mb-2 text-xs font-bold tracking-[0.3em] text-ocean uppercase"
                        >
                            System Access
                        </motion.div>
                        <h1 className="text-3xl font-bold text-pearl-glow font-display tracking-tight">
                            ANTIGRAVITY
                        </h1>
                    </div>

                    <form onSubmit={handleLogin} className="space-y-6">
                        {/* Email Field */}
                        <div className="space-y-2 group">
                            <div className="relative">
                                <Mail className="absolute left-3 top-3.5 h-4 w-4 text-muted-foreground group-focus-within:text-ocean transition-colors" />
                                <input
                                    type="email"
                                    placeholder="IDENTITY"
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    className="w-full bg-midnight/30 border-b border-white/10 px-10 py-3 text-sm tracking-wide text-pearl placeholder:text-muted-foreground focus:outline-none focus:border-ocean focus:bg-midnight/50 transition-all duration-300 rounded-t-sm"
                                    disabled={isLoading}
                                />
                                <div className="absolute bottom-0 left-0 h-[1px] w-0 bg-ocean group-focus-within:w-full transition-all duration-500" />
                            </div>
                        </div>

                        {/* Password Field */}
                        <div className="space-y-2 group">
                            <div className="relative">
                                <Lock className="absolute left-3 top-3.5 h-4 w-4 text-muted-foreground group-focus-within:text-ocean transition-colors" />
                                <input
                                    type={showPassword ? "text" : "password"}
                                    placeholder="CREDENTIALS"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    className="w-full bg-midnight/30 border-b border-white/10 px-10 py-3 text-sm tracking-wide text-pearl placeholder:text-muted-foreground focus:outline-none focus:border-ocean focus:bg-midnight/50 transition-all duration-300 rounded-t-sm"
                                    disabled={isLoading}
                                />
                                <button
                                    type="button"
                                    onClick={() => setShowPassword(!showPassword)}
                                    className="absolute right-3 top-3.5 text-muted-foreground hover:text-pearl transition-colors"
                                >
                                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                                </button>
                                <div className="absolute bottom-0 left-0 h-[1px] w-0 bg-ocean group-focus-within:w-full transition-all duration-500" />
                            </div>
                        </div>

                        <div className="flex items-center justify-between text-xs text-muted-foreground">
                            <label className="flex items-center gap-2 cursor-pointer hover:text-pearl transition-colors">
                                <input type="checkbox" className="rounded border-white/20 bg-midnight/50 accent-ocean" />
                                <span>Keep link active</span>
                            </label>
                            <a href="#" className="hover:text-ocean transition-colors">Lost credentials?</a>
                        </div>

                        <NeonButton
                            className="w-full"
                            type="submit"
                            disabled={isLoading}
                        >
                            {isLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : "INITIATE SESSION"}
                        </NeonButton>
                    </form>

                    <div className="mt-8 text-center text-xs text-muted-foreground">
                        NO ACCOUNT? <Link to="/register" className="text-ocean hover:text-white underline decoration-ocean/50 underline-offset-4 transition-all">REQUEST ACCESS</Link>
                    </div>
                </GlassPanel>
            </motion.div>
        </div>
    );
};

export default AntigravityLogin;
