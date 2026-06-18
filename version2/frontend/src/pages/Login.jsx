import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Eye, EyeOff, ArrowLeft, Database, MessageSquare, BarChart3 } from "lucide-react";
import { motion } from "framer-motion";
import { useAuth } from "@/store/authStore";
import toast from "react-hot-toast";
import Logo from "@/components/common/Logo";

function FeatureItem({
  icon: Icon,
  title,
  description,
}) {
  return (
    <motion.div
      variants={{
        hidden: { opacity: 0, y: 10 },
        visible: { opacity: 1, y: 0, transition: { duration: 0.5 } },
      }}
      className="flex items-start gap-4 rounded-2xl p-4 border border-white/10 backdrop-blur-md shadow-xl transition-all hover:border-white/20"
      style={{
        background: "linear-gradient(110deg, rgba(0, 0, 0, 0.55) 0%, rgba(0, 0, 0, 0.25) 50%, rgba(0, 0, 0, 0.05) 100%)"
      }}
    >
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white/10 text-[#f06f1c]">
        <Icon className="h-5 w-5" />
      </div>
      <div className="space-y-1">
        <h4 className="text-sm font-semibold text-white">{title}</h4>
        <p className="text-xs text-zinc-200 leading-relaxed">{description}</p>
      </div>
    </motion.div>
  );
}

function SocialButton({
  icon,
  label,
  onClick,
  disabled,
  comingSoon = false
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled || comingSoon}
      className={`flex h-12 w-full items-center justify-center gap-2 rounded-xl border border-white/10 bg-[#18181a] text-sm font-medium text-white transition-colors disabled:opacity-50 ${
        comingSoon 
          ? "cursor-not-allowed opacity-60" 
          : "cursor-pointer hover:bg-white/5 active:scale-[0.98]"
      }`}
    >
      {icon}
      <span>{label}</span>
      {comingSoon && (
        <span className="rounded bg-white/10 px-1.5 py-0.5 text-[10px] font-semibold text-white/50">
          Soon
        </span>
      )}
    </button>
  );
}

function InputGroup({
  label,
  placeholder,
  type,
  value,
  onChange,
  rightElement,
  disabled
}) {
  return (
    <div className="space-y-1.5">
      <label className="block text-sm font-medium text-white">{label}</label>
      <div className="relative">
        <input
          type={type}
          placeholder={placeholder}
          value={value}
          onChange={onChange}
          disabled={disabled}
          className="h-11 w-full rounded-xl border border-white/10 bg-[#18181a] px-4 text-sm text-white placeholder:text-white/40 focus:border-[#f06f1c]/50 focus:ring-2 focus:ring-[#f06f1c]/30 focus:outline-none transition-all disabled:opacity-50"
        />
        {rightElement && (
          <div className="absolute right-3 top-1/2 -translate-y-1/2">
            {rightElement}
          </div>
        )}
      </div>
    </div>
  );
}

export default function LoginPage() {
  const [showPassword, setShowPassword] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const { login, googleLogin } = useAuth();
  const navigate = useNavigate();

  const handleGoogleLogin = () => {
    try {
      googleLogin();
    } catch (error) {
      console.error('Google login error:', error);
      toast.error('Failed to initiate Google login');
    }
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    if (!email || !password) {
      toast.error("Please fill in all fields");
      return;
    }

    setIsLoading(true);
    try {
      const result = await login(email, password, true); // rememberMe default true
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
    <main className="flex min-h-screen w-full bg-[#0d0d0f] selection:bg-[#D89B14]/30 p-2 transition-all duration-500 lg:h-screen lg:overflow-hidden lg:p-4">
      {/* Left Column (Hero) */}
      <div 
        className="relative hidden w-[52%] flex-col items-center justify-end overflow-hidden rounded-3xl pb-32 px-12 shadow-2xl h-full lg:flex border border-white/5"
        style={{ 
          backgroundImage: "linear-gradient(180deg, #080200 0%, #4b1702 35%, #b04409 65%, #f06f1c 85%, #f9bc59 100%)",
          backgroundRepeat: "no-repeat"
        }}
      >
        <Link
          to="/"
          className="absolute left-8 top-8 z-20 flex items-center gap-2 text-sm font-medium text-white/60 hover:text-white transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Home
        </Link>

        <motion.div
          initial="hidden"
          animate="visible"
          variants={{
            hidden: { opacity: 0 },
            visible: {
              opacity: 1,
              transition: { staggerChildren: 0.15, delayChildren: 0.2 },
            },
          }}
          className="relative z-10 w-full max-w-sm space-y-8"
        >
          <motion.div
            variants={{
              hidden: { opacity: 0, y: 10 },
              visible: { opacity: 1, y: 0, transition: { duration: 0.5 } },
            }}
          >
            <Logo size={24} showText={true} />
          </motion.div>

          <motion.div
            variants={{
              hidden: { opacity: 0, y: 10 },
              visible: { opacity: 1, y: 0, transition: { duration: 0.5 } },
            }}
          >
            <h1 className="text-4xl font-semibold tracking-tight text-white leading-tight">
              A new way to interact with data
            </h1>
            <p className="mt-2 text-sm leading-relaxed text-white/60">
              Signal connects directly to your databases and turns tables into interactive conversational insights.
            </p>
          </motion.div>

          <div className="space-y-3">
            <FeatureItem
              icon={Database}
              title="Universal Connectors"
              description="Seamlessly link Google Sheets, PostgreSQL, Excel, or CSV files in seconds."
            />
            <FeatureItem
              icon={MessageSquare}
              title="Conversational Analytics"
              description="Ask questions in plain English and get instant queries, answers, and summaries."
            />
            <FeatureItem
              icon={BarChart3}
              title="Interactive Visualizations"
              description="Dynamically generate high-fidelity charts, graphs, and live reports from your inquiries."
            />
          </div>
        </motion.div>
      </div>

      {/* Right Column (Form) */}
      <div className="flex flex-1 flex-col items-center justify-center overflow-y-auto px-4 py-12 sm:px-12 lg:overflow-hidden lg:px-16 lg:py-6 xl:px-24">
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          className="w-full max-w-xl space-y-8 sm:space-y-10 lg:space-y-6"
        >
          <div>
            <h2 className="text-3xl font-medium tracking-tight text-white">
              Sign In to Signal
            </h2>
            <p className="mt-1.5 text-sm text-white/40">
              Enter your credentials to access your workspace.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <SocialButton
              label="Google"
              onClick={handleGoogleLogin}
              disabled={isLoading}
              icon={
                <svg className="h-5 w-5" viewBox="0 0 24 24">
                  <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4" />
                  <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
                  <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
                  <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
                </svg>
              }
            />
            <SocialButton
              label="GitHub"
              disabled={isLoading}
              comingSoon={true}
              onClick={() => toast.error("GitHub login not yet configured")}
              icon={
                <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
                </svg>
              }
            />
          </div>

          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-white/10" />
            </div>
            <div className="relative flex justify-center text-xs font-medium uppercase tracking-widest text-white/40">
              <span className="bg-[#0d0d0f] px-4">Or</span>
            </div>
          </div>

          <form onSubmit={handleLogin} className="space-y-4">
            <InputGroup
              label="Email"
              type="email"
              placeholder="ex. alex@signal.io"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={isLoading}
            />
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="block text-sm font-medium text-white">Password</label>
                <Link to="#" className="text-xs text-[#D89B14] hover:text-[#C08A12] transition-colors">
                  Forgot password?
                </Link>
              </div>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  placeholder="Secure your account"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={isLoading}
                  className="h-11 w-full rounded-xl border-none bg-[#18181a] px-4 pr-10 text-sm text-white placeholder:text-white/20 focus:outline-none focus:ring-2 focus:ring-[#D89B14]/50 transition-all disabled:opacity-50"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 flex h-full items-center justify-center text-white/40 hover:text-white transition-colors"
                >
                  {showPassword ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="mt-6 h-14 w-full rounded-xl bg-[#f06f1c] text-white font-semibold transition-all hover:bg-[#b04409] active:scale-[0.98] disabled:opacity-50 disabled:active:scale-100"
            >
              {isLoading ? "Authenticating..." : "Access Account"}
            </button>
          </form>

          <p className="text-center text-sm text-white/50">
            Need to register?{" "}
            <Link
              to="/register"
              className="font-medium text-white hover:underline underline-offset-4"
            >
              Sign up
            </Link>
          </p>
        </motion.div>
      </div>
    </main>
  );
}
