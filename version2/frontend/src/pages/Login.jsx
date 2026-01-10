import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
    ArrowLeft,
    Eye,
    EyeOff,
    Mail,
    Lock
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { useAuth } from "@/store/authStore";
import AuthPreview from "@/components/AuthPreview";
import toast from "react-hot-toast";

export default function LoginPage() {
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
                toast.success("Welcome back!");
                navigate("/app/dashboard");
            } else {
                toast.error(result.error || "Login failed");
            }
        } catch (error) {
            toast.error("An unexpected error occurred");
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="h-screen bg-[#09090b] text-zinc-100 flex flex-col md:flex-row overflow-hidden relative">
            {/* Left Column: Login Form */}
            <div className="w-full md:w-1/2 flex flex-col justify-between p-8 md:p-12 lg:p-16 z-10 bg-[#09090b]">
                <div className="flex-1 flex items-center">
                    <div className="max-w-[400px] w-full mx-auto space-y-8">
                        <Link
                            to="/"
                            className="inline-flex items-center gap-2 text-sm text-zinc-400 hover:text-white transition-colors group"
                        >
                            <ArrowLeft className="w-4 h-4 transition-transform group-hover:-translate-x-1" />
                            Back to Home
                        </Link>
                        <div className="space-y-2">
                            <h1 className="text-3xl font-bold tracking-tight text-white">Welcome Back</h1>
                            <p className="text-zinc-400 text-base">
                                Enter your credentials to access your account.
                            </p>
                        </div>

                        <form className="space-y-6" onSubmit={handleLogin}>
                            <div className="space-y-2">
                                <Label htmlFor="email" className="text-zinc-300 text-base">Email</Label>
                                <div className="relative">
                                    <Mail className="absolute left-3.5 top-3.5 h-4 w-4 text-zinc-500" />
                                    <Input
                                        id="email"
                                        type="email"
                                        placeholder="Email address"
                                        className="bg-zinc-900/50 border-zinc-800 pl-11 h-11 text-base focus:ring-indigo-500/20 focus:border-indigo-500 transition-all text-white"
                                        value={email}
                                        onChange={(e) => setEmail(e.target.value)}
                                        disabled={isLoading}
                                    />
                                </div>
                            </div>

                            <div className="space-y-2">
                                <div className="flex items-center justify-between">
                                    <Label htmlFor="password" text-zinc-300 className="text-base">Password</Label>
                                    <Link to="#" className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors">
                                        Forgot password?
                                    </Link>
                                </div>
                                <div className="relative">
                                    <Lock className="absolute left-3.5 top-3.5 h-4 w-4 text-zinc-500" />
                                    <Input
                                        id="password"
                                        type={showPassword ? "text" : "password"}
                                        placeholder="Password"
                                        className="bg-zinc-900/50 border-zinc-800 pl-11 h-11 text-base focus:ring-indigo-500/20 focus:border-indigo-500 transition-all text-white"
                                        value={password}
                                        onChange={(e) => setPassword(e.target.value)}
                                        disabled={isLoading}
                                    />
                                    <button
                                        type="button"
                                        onClick={() => setShowPassword(!showPassword)}
                                        className="absolute right-3.5 top-3.5 text-zinc-500 hover:text-zinc-300"
                                        disabled={isLoading}
                                    >
                                        {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                                    </button>
                                </div>
                            </div>

                            <div className="flex items-center space-x-2">
                                <Checkbox id="remember" className="w-4 h-4 border-zinc-700 data-[state=checked]:bg-indigo-600 data-[state=checked]:border-indigo-600" />
                                <label htmlFor="remember" className="text-sm text-zinc-400 cursor-pointer select-none">
                                    Remember me
                                </label>
                            </div>

                            <Button
                                type="submit"
                                className="w-full h-11 bg-zinc-100 text-zinc-900 hover:bg-zinc-200 text-base font-semibold transition-all shadow-lg shadow-indigo-500/5"
                                disabled={isLoading}
                            >
                                {isLoading ? "Signing In..." : "Sign In"}
                            </Button>

                            <div className="relative">
                                <div className="absolute inset-0 flex items-center">
                                    <span className="w-full border-t border-zinc-800"></span>
                                </div>
                                <div className="relative flex justify-center text-xs uppercase">
                                    <span className="bg-[#09090b] px-2 text-zinc-500">Or login with</span>
                                </div>
                            </div>

                            <div className="flex flex-col gap-2">
                                <Button variant="outline" type="button" className="w-full border-zinc-800 bg-zinc-900/50 hover:bg-zinc-800 text-zinc-300 h-11 text-base transition-all">
                                    <svg className="mr-2 h-4 w-4" viewBox="0 0 24 24">
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
                                    Google
                                </Button>
                            </div>
                        </form>
                        <p className="text-center text-base text-zinc-400">
                            Don't have an account?{" "}
                            <Link to="/register" className="text-indigo-400 hover:text-indigo-300 font-medium">
                                Register
                            </Link>
                        </p>
                    </div>
                </div>
                <div className="mt-8 flex flex-col sm:flex-row items-center justify-between text-xs text-zinc-600 gap-4">
                    <p>© 2026 Datasage Inc.</p>
                    <div className="flex gap-6 uppercase tracking-wider font-bold">
                        <Link to="#" className="hover:text-zinc-400 transition-colors">Privacy</Link>
                        <Link to="#" className="hover:text-zinc-400 transition-colors">Terms</Link>
                    </div>
                </div>
            </div>
            {/* Right Column: Visual Preview */}
            <AuthPreview />
        </div>

    );
}
