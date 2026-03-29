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

                    <div className="mt-6 relative">
                        <div className="absolute inset-0 flex items-center">
                            <span className="w-full border-t border-white/10"></span>
                        </div>
                        <div className="relative flex justify-center text-xs uppercase">
                            <span className="bg-noir px-2 text-muted-foreground">Or continue with</span>
                        </div>
                    </div>

                    <button
                        type="button"
                        onClick={() => useAuth().googleLogin()}
                        className="mt-4 w-full flex items-center justify-center gap-3 px-4 py-3 bg-midnight/50 border border-white/10 hover:border-white/20 rounded-xl transition-all text-pearl"
                    >
                        <svg className="w-5 h-5" viewBox="0 0 24 24">
                            <path
                                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                                fill="#4285F4"
                            />
                            <path
                                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                                fill="#34A853"
                            />
                            <path
                                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                                fill="#FBBC05"
                            />
                            <path
                                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 8.32-4.53z"
                                fill="#EA4335"
                            />
                        </svg>
                        <span className="text-sm font-medium">Google</span>
                    </button>

                    <div className="mt-8 text-center text-xs text-muted-foreground">
                        NO ACCOUNT? <Link to="/register" className="text-ocean hover:text-white underline decoration-ocean/50 underline-offset-4 transition-all">REQUEST ACCESS</Link>
                    </div>
                </GlassPanel>
            </motion.div>
        </div>
    );
};

export default AntigravityLogin;
